"""HTTP-facing orchestration for persisted, evidence-validated diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

from knowledge.schema.diagnosis_schema import (
    DiagnosisAnswerDecision,
    DiagnosisContinueRequest,
    DiagnosisDecision,
    DiagnosisInsufficientDecision,
    DiagnosisStartRequest,
)
from knowledge.services.query_service import QueryService
from knowledge.utils.diagnosis_session_util import (
    DiagnosisSessionError,
    DiagnosisSessionRepository,
    DiagnosisSessionStateError,
)
from knowledge.utils.sse_util import SSEEvent, close_sse_stream, push_sse_event
from knowledge.utils.task_util import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_DEDUPLICATED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PROCESSING,
    set_task_result,
    update_task_status,
)


_DECISION_ADAPTER = TypeAdapter(DiagnosisDecision)


class DiagnosisExecutionError(RuntimeError):
    """A graph or persistence failure that must not become a diagnosis result."""


@dataclass(frozen=True)
class DiagnosisExecutionResult:
    session: dict[str, Any]
    decision: Optional[dict[str, Any]]
    idempotent: bool
    running: bool = False
    active_task_id: Optional[str] = None


class DiagnosisService:
    """Run one diagnosis turn at a time and persist only validated decisions."""

    def __init__(
        self,
        query_service: Optional[QueryService] = None,
        repository: Optional[DiagnosisSessionRepository] = None,
    ):
        self._query_service = query_service or QueryService()
        self._repository = repository or DiagnosisSessionRepository()

    @property
    def repository(self) -> DiagnosisSessionRepository:
        return self._repository

    def start_session(
        self, visitor_id: str, request: DiagnosisStartRequest, request_id: str
    ) -> tuple[dict[str, Any], bool]:
        return self._repository.create_or_get_session(visitor_id, request, request_id)

    def submit_answers(
        self, visitor_id: str, request: DiagnosisContinueRequest
    ) -> tuple[dict[str, Any], bool]:
        result = self._repository.save_answers(visitor_id, request)
        return result.session, result.idempotent

    def run_task(
        self,
        *,
        diagnosis_id: str,
        visitor_id: str,
        expected_revision: int,
        inference_request_id: str,
        task_id: str,
        is_stream: bool,
    ) -> DiagnosisExecutionResult:
        """Execute one graph turn and emit only persisted diagnosis SSE events."""
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        try:
            result = self._run_turn(
                diagnosis_id=diagnosis_id,
                visitor_id=visitor_id,
                expected_revision=expected_revision,
                inference_request_id=inference_request_id,
                task_id=task_id,
                is_stream=is_stream,
            )
            payload = self.session_payload(result.session)
            if result.running:
                payload["processing"] = True
                payload["active_task_id"] = result.active_task_id
            set_task_result(task_id, "diagnosis", payload)
            if is_stream and result.decision is not None:
                push_sse_event(task_id, SSEEvent.DIAGNOSIS, payload)
            update_task_status(
                task_id, TASK_STATUS_DEDUPLICATED if result.running else TASK_STATUS_COMPLETED
            )
            if is_stream:
                push_sse_event(
                    task_id,
                    SSEEvent.FINAL,
                    {
                        "status": "deduplicated" if result.running else "completed",
                        "diagnosis_id": diagnosis_id,
                        "idempotent": result.idempotent,
                        "processing": result.running,
                        "active_task_id": result.active_task_id,
                    },
                )
            return result
        except Exception as exc:
            set_task_result(task_id, "error", str(exc))
            update_task_status(task_id, TASK_STATUS_FAILED)
            if is_stream:
                push_sse_event(
                    task_id,
                    SSEEvent.ERROR,
                    {"code": "diagnosis_failed", "message": "诊断处理失败，请稍后重试。"},
                )
                push_sse_event(
                    task_id,
                    SSEEvent.FINAL,
                    {"status": "failed", "diagnosis_id": diagnosis_id},
                )
            raise
        finally:
            if is_stream:
                close_sse_stream(task_id)

    def run_background_task(self, **kwargs: Any) -> None:
        """Background-task wrapper: failure is published to SSE/task state, not re-raised."""
        try:
            self.run_task(**kwargs)
        except Exception:
            return

    def _run_turn(
        self,
        *,
        diagnosis_id: str,
        visitor_id: str,
        expected_revision: int,
        inference_request_id: str,
        task_id: str,
        is_stream: bool,
    ) -> DiagnosisExecutionResult:
        claim = self._repository.claim_inference(
            diagnosis_id,
            visitor_id,
            inference_request_id,
            expected_revision,
            task_id=task_id,
        )
        if claim.idempotent:
            return DiagnosisExecutionResult(
                session=claim.session,
                decision=self.decision_from_session(claim.session),
                idempotent=True,
            )
        if claim.running:
            return DiagnosisExecutionResult(
                session=claim.session,
                decision=None,
                idempotent=False,
                running=True,
                active_task_id=claim.active_task_id,
            )

        try:
            self._push_progress(task_id, is_stream, "retrieval", "正在检索 K1 本地资料")
            self._push_progress(task_id, is_stream, "decision", "正在生成诊断决策")
            state = self._query_service.build_diagnosis_graph_state(
                diagnosis_id,
                visitor_id,
                task_id,
                is_stream,
                repository=self._repository,
            )
            graph_result = self._query_service.run_diagnosis_graph(state)
            if graph_result.get("diagnosis_status") == "system_error":
                raise DiagnosisExecutionError(
                    graph_result.get("diagnosis_system_error", {}).get(
                        "message", "诊断模型或校验服务不可用"
                    )
                )

            self._push_progress(task_id, is_stream, "validation", "正在校验证据与安全边界")
            decision = self._validated_decision(graph_result)
            status = graph_result.get("diagnosis_status")
            validation_passed = graph_result.get("diagnosis_validation_passed") is True
            if decision.action == "ask":
                if status != "validated" or not validation_passed:
                    raise DiagnosisExecutionError("未通过校验的问题组不能写入诊断会话")
                session = self._repository.save_question_round(
                    diagnosis_id,
                    visitor_id,
                    decision,
                    expected_revision,
                    execution_request_id=inference_request_id,
                )
            else:
                if status == "validation_rejected" and decision.action != "insufficient":
                    raise DiagnosisExecutionError("校验拒绝结果不能保存为维修结论")
                if status not in {"validated", "validation_rejected"}:
                    raise DiagnosisExecutionError("诊断结果未通过允许的验证路径")
                metadata = None
                if status == "validation_rejected":
                    metadata = {
                        "validation_status": status,
                        "rejection": graph_result.get("diagnosis_validation_error", {}),
                    }
                session = self._repository.save_final_result(
                    diagnosis_id,
                    visitor_id,
                    decision,
                    expected_revision,
                    execution_request_id=inference_request_id,
                    result_metadata=metadata,
                )
            return DiagnosisExecutionResult(
                session=session,
                decision=decision.model_dump(mode="json"),
                idempotent=False,
            )
        except (DiagnosisExecutionError, DiagnosisSessionError):
            self._repository.release_inference(diagnosis_id, visitor_id, inference_request_id)
            raise
        except Exception as exc:
            self._repository.release_inference(diagnosis_id, visitor_id, inference_request_id)
            raise DiagnosisExecutionError("诊断图执行失败") from exc

    @staticmethod
    def _validated_decision(state: dict[str, Any]) -> DiagnosisDecision:
        payload = state.get("diagnosis_validated")
        if not isinstance(payload, dict) or not payload:
            raise DiagnosisExecutionError("诊断图未返回可验证的结构化结果")
        try:
            return _DECISION_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            raise DiagnosisExecutionError("诊断图返回的验证结果结构无效") from exc

    @staticmethod
    def decision_from_session(session: dict[str, Any]) -> Optional[dict[str, Any]]:
        result = session.get("result")
        if isinstance(result, dict) and result:
            return result
        rounds = session.get("rounds")
        if isinstance(rounds, list):
            for round_record in reversed(rounds):
                if isinstance(round_record, dict) and not round_record.get("answers"):
                    questions = round_record.get("questions")
                    if isinstance(questions, list):
                        return {"action": "ask", "questions": questions}
        return None

    @classmethod
    def session_payload(cls, session: dict[str, Any]) -> dict[str, Any]:
        """Return recoverable client state without storage internals or visitor ID."""
        decision = cls.decision_from_session(session)
        return {
            "diagnosis_id": session.get("diagnosis_id"),
            "device_id": session.get("device_id"),
            "device_model": session.get("device_model"),
            "original_problem": session.get("original_problem"),
            "status": session.get("status"),
            "clarification_round": session.get("clarification_count", 0),
            "revision": session.get("revision"),
            "facts": session.get("facts", []),
            "rounds": session.get("rounds", []),
            "decision": decision,
            "feedback": session.get("feedback"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
        }

    @staticmethod
    def _push_progress(task_id: str, is_stream: bool, stage: str, message: str) -> None:
        if is_stream:
            push_sse_event(task_id, SSEEvent.PROGRESS, {"stage": stage, "message": message})
