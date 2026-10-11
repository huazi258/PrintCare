"""MongoDB persistence for diagnosis sessions.

This module deliberately owns diagnosis records separately from the legacy
``chat_message`` collection.  It is storage-only: LLM decisions, retrieval
evidence verification, HTTP routes, and SSE events are introduced by later
T2 tasks.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from knowledge.core.devices import resolve_supported_device
from knowledge.schema.diagnosis_schema import (
    DiagnosisAnswerDecision,
    DiagnosisAskDecision,
    DiagnosisContinueRequest,
    DiagnosisInsufficientDecision,
    DiagnosisStartRequest,
)
from knowledge.utils.client.storage_clients import StorageClients


DIAGNOSIS_COLLECTION_NAME = "diagnosis_session"
TERMINAL_STATUSES = frozenset({"resolved", "insufficient", "ended"})

_ALLOWED_STATUS_TRANSITIONS = {
    "in_progress": frozenset({"pending_verification", "insufficient", "ended"}),
    "pending_verification": frozenset({"resolved", "unresolved", "ended"}),
    "unresolved": frozenset({"in_progress", "ended"}),
    "resolved": frozenset(),
    "insufficient": frozenset(),
    "ended": frozenset(),
}


class DiagnosisSessionError(RuntimeError):
    """Base error for diagnosis session persistence."""


class DiagnosisSessionNotFoundError(DiagnosisSessionError):
    """Raised when a visitor cannot access the requested session."""


class DiagnosisSessionConflictError(DiagnosisSessionError):
    """Raised when the caller uses a stale session revision."""


class DiagnosisSessionStateError(DiagnosisSessionError):
    """Raised when an operation is invalid for the current lifecycle state."""


class DiagnosisSessionStorageError(DiagnosisSessionError):
    """Raised when MongoDB cannot safely complete a persistence operation."""


@dataclass(frozen=True)
class AnswerSubmissionResult:
    """Result of an answer write, including idempotency information."""

    session: dict[str, Any]
    idempotent: bool
    request_record: dict[str, Any]


@dataclass(frozen=True)
class InferenceClaimResult:
    """Outcome of atomically acquiring (or recognising) an inference lease."""

    session: dict[str, Any]
    idempotent: bool
    running: bool


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _public_document(document: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if document is None:
        return None
    result = deepcopy(document)
    result.pop("_id", None)
    return result


class DiagnosisSessionRepository:
    """Atomic, visitor-scoped access to the ``diagnosis_session`` collection."""

    def __init__(self, collection: Optional[Collection] = None):
        self._collection = (
            collection
            if collection is not None
            else StorageClients.get_mongo_db()[DIAGNOSIS_COLLECTION_NAME]
        )

    def ensure_indexes(self) -> None:
        """Create the small set of indexes required by the access patterns."""
        try:
            self._collection.create_index(
                [("diagnosis_id", ASCENDING)],
                name="diagnosis_id_unique",
                unique=True,
            )
            self._collection.create_index(
                [("visitor_id", ASCENDING), ("updated_at", DESCENDING)],
                name="visitor_updated_at",
            )
            self._collection.create_index(
                [("visitor_id", ASCENDING), ("creation_request_id", ASCENDING)],
                name="visitor_creation_request_unique",
                unique=True,
                partialFilterExpression={"creation_request_id": {"$type": "string"}},
            )
        except Exception as exc:
            raise DiagnosisSessionStorageError("无法创建诊断会话索引") from exc

    def create_session(
        self,
        visitor_id: str,
        request: DiagnosisStartRequest,
        *,
        diagnosis_id: Optional[str] = None,
        creation_request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create one visitor-owned, in-progress diagnosis session."""
        self._require_nonblank("visitor_id", visitor_id)
        self.ensure_indexes()

        device = resolve_supported_device(request.device_id)
        now = _utc_now()
        document = {
            "diagnosis_id": diagnosis_id or str(uuid4()),
            "visitor_id": visitor_id,
            "device_id": device.device_id,
            "device_model": device.device_model,
            "original_problem": request.original_problem,
            "status": "in_progress",
            "facts": [],
            "rounds": [],
            "clarification_count": 0,
            "result": None,
            "result_metadata": None,
            "feedback": None,
            "revision": 0,
            # A Mongo-backed lease prevents two callers from running the same
            # graph concurrently.  It is intentionally not a diagnosis result.
            "execution": None,
            # Keep every processed client submission, not only the latest ID:
            # delayed retries must remain idempotent after newer rounds finish.
            "processed_requests": [],
            "created_at": now,
            "updated_at": now,
        }
        if creation_request_id is not None:
            document["creation_request_id"] = creation_request_id
        try:
            self._collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise DiagnosisSessionConflictError("诊断会话标识已存在") from exc
        except Exception as exc:
            raise DiagnosisSessionStorageError("无法创建诊断会话") from exc
        return _public_document(document)  # type: ignore[return-value]

    def create_or_get_session(
        self, visitor_id: str, request: DiagnosisStartRequest, request_id: str
    ) -> tuple[dict[str, Any], bool]:
        """Create a session once for a retried start request.

        The unique visitor/request index is the race-safe authority; the
        initial read is only a fast path for ordinary retries.
        """
        self._require_nonblank("request_id", request_id)
        try:
            existing = self._collection.find_one(
                {"visitor_id": visitor_id, "creation_request_id": request_id}
            )
        except Exception as exc:
            raise DiagnosisSessionStorageError("无法读取诊断创建请求") from exc
        if existing is not None:
            return _public_document(existing), True  # type: ignore[return-value]
        try:
            return self.create_session(
                visitor_id, request, creation_request_id=request_id
            ), False
        except DiagnosisSessionConflictError:
            try:
                existing = self._collection.find_one(
                    {"visitor_id": visitor_id, "creation_request_id": request_id}
                )
            except Exception as exc:
                raise DiagnosisSessionStorageError("无法恢复重复诊断创建请求") from exc
            if existing is None:
                raise
            return _public_document(existing), True  # type: ignore[return-value]

    def get_session(self, diagnosis_id: str, visitor_id: str) -> Optional[dict[str, Any]]:
        """Read one session only when it belongs to the supplied visitor."""
        document = self._find_owned_session(diagnosis_id, visitor_id)
        return _public_document(document)

    def list_sessions(self, visitor_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return one visitor's sessions, most recently updated first."""
        self._require_nonblank("visitor_id", visitor_id)
        if limit < 1:
            raise ValueError("limit 必须大于 0")
        try:
            cursor = (
                self._collection.find({"visitor_id": visitor_id})
                .sort("updated_at", DESCENDING)
                .limit(limit)
            )
            return [_public_document(document) for document in cursor]  # type: ignore[misc]
        except Exception as exc:
            raise DiagnosisSessionStorageError("无法读取诊断会话列表") from exc

    def claim_inference(
        self,
        diagnosis_id: str,
        visitor_id: str,
        request_id: str,
        expected_revision: int,
        *,
        lease_seconds: int = 300,
    ) -> InferenceClaimResult:
        """Acquire one revision-scoped graph execution lease atomically.

        Completed request records make delayed client retries idempotent.  A
        bounded lease makes a process crash recoverable without a second task
        queue or distributed lock.
        """
        self._require_nonblank("request_id", request_id)
        session = self._get_required_session(diagnosis_id, visitor_id)
        completed = self._find_processed_request(session, request_id)
        if completed is not None:
            return InferenceClaimResult(
                session=_public_document(session),  # type: ignore[arg-type]
                idempotent=True,
                running=False,
            )
        self._require_expected_revision(session, expected_revision)
        self._require_status(session, "in_progress")

        now = _utc_now()
        lease = {
            "request_id": request_id,
            "revision": expected_revision,
            "started_at": now,
            "expires_at": now + timedelta(seconds=lease_seconds),
        }
        updated = self._find_one_and_update(
            {
                "diagnosis_id": diagnosis_id,
                "visitor_id": visitor_id,
                "revision": expected_revision,
                "status": "in_progress",
                "execution": None,
            },
            {"$set": {"execution": lease, "updated_at": now}},
        )
        if updated is not None:
            return InferenceClaimResult(
                session=_public_document(updated),  # type: ignore[arg-type]
                idempotent=False,
                running=False,
            )

        latest = self._get_required_session(diagnosis_id, visitor_id)
        completed = self._find_processed_request(latest, request_id)
        if completed is not None:
            return InferenceClaimResult(
                session=_public_document(latest),  # type: ignore[arg-type]
                idempotent=True,
                running=False,
            )
        active = latest.get("execution")
        if isinstance(active, dict):
            expires_at = active.get("expires_at")
            if isinstance(expires_at, datetime) and expires_at <= now:
                reclaimed = self._find_one_and_update(
                    {
                        "diagnosis_id": diagnosis_id,
                        "visitor_id": visitor_id,
                        "revision": expected_revision,
                        "status": "in_progress",
                        "execution.request_id": active.get("request_id"),
                        "execution.expires_at": {"$lt": now},
                    },
                    {"$set": {"execution": lease, "updated_at": now}},
                )
                if reclaimed is not None:
                    return InferenceClaimResult(
                        session=_public_document(reclaimed),  # type: ignore[arg-type]
                        idempotent=False,
                        running=False,
                    )
            if active.get("request_id") == request_id:
                return InferenceClaimResult(
                    session=_public_document(latest),  # type: ignore[arg-type]
                    idempotent=False,
                    running=True,
                )
            raise DiagnosisSessionConflictError("诊断会话已有正在执行的推理任务")
        self._raise_after_failed_write(diagnosis_id, visitor_id, expected_revision)

    def release_inference(
        self, diagnosis_id: str, visitor_id: str, request_id: str
    ) -> None:
        """Release an unsuccessful lease without advancing session revision."""
        now = _utc_now()
        updated = self._find_one_and_update(
            {
                "diagnosis_id": diagnosis_id,
                "visitor_id": visitor_id,
                "execution.request_id": request_id,
            },
            {"$set": {"execution": None, "updated_at": now}},
        )
        if updated is None:
            # A completed write may have cleared the lease between error
            # handling paths; do not turn that safe state into a new failure.
            session = self._get_required_session(diagnosis_id, visitor_id)
            if session.get("execution") is not None:
                raise DiagnosisSessionStateError("诊断推理执行占用已发生变化")

    def save_question_round(
        self,
        diagnosis_id: str,
        visitor_id: str,
        decision: DiagnosisAskDecision,
        expected_revision: int,
        *,
        execution_request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Atomically append one generated question group and increment its count."""
        session = self._get_required_session(diagnosis_id, visitor_id)
        self._require_expected_revision(session, expected_revision)
        self._require_status(session, "in_progress")
        if session["clarification_count"] >= 3:
            raise DiagnosisSessionStateError("已达到三轮追问上限")
        if session["rounds"] and not session["rounds"][-1].get("answers"):
            raise DiagnosisSessionStateError("当前问题组尚未完成回答")

        now = _utc_now()
        round_record = {
            "round_index": session["clarification_count"] + 1,
            "questions": [question.model_dump(mode="json") for question in decision.questions],
            "answers": [],
            "created_at": now,
            "answered_at": None,
        }
        query = {
                "diagnosis_id": diagnosis_id,
                "visitor_id": visitor_id,
                "revision": expected_revision,
                "status": "in_progress",
                # This condition must remain in the atomic write filter: a
                # concurrent caller cannot append a fourth round after its
                # stale pre-read passed the guard above.
                "clarification_count": {"$lt": 3},
            }
        changes: dict[str, Any] = {
            "$push": {"rounds": round_record},
            "$inc": {"clarification_count": 1, "revision": 1},
            "$set": {"updated_at": now},
        }
        if execution_request_id is not None:
            query["execution.request_id"] = execution_request_id
            changes["$set"]["execution"] = None
            changes["$push"]["processed_requests"] = self._inference_request_record(
                execution_request_id, "ask", expected_revision, now
            )
        updated = self._find_one_and_update(
            query,
            changes,
        )
        if updated is None:
            self._raise_after_failed_write(diagnosis_id, visitor_id, expected_revision)
        return _public_document(updated)  # type: ignore[return-value]

    def save_answers(
        self,
        visitor_id: str,
        request: DiagnosisContinueRequest,
    ) -> AnswerSubmissionResult:
        """Save a batch answer exactly once using revision-guarded MongoDB update."""
        session = self._get_required_session(request.diagnosis_id, visitor_id)
        previous_request = self._find_processed_request(session, request.request_id)
        if previous_request is not None:
            return AnswerSubmissionResult(
                session=_public_document(session),  # type: ignore[arg-type]
                idempotent=True,
                request_record=previous_request,
            )

        self._require_expected_revision(session, request.expected_revision)
        self._require_status(session, "in_progress")
        current_round = self._current_unanswered_round(session)
        if current_round is None:
            raise DiagnosisSessionStateError("当前没有等待回答的问题组")
        self._validate_answers_for_current_round(request, current_round)

        now = _utc_now()
        answer_records = [
            {
                **answer.model_dump(mode="json"),
                "submitted_at": now,
            }
            for answer in request.answers
        ]
        fact_records = [
            {
                "round_index": current_round["round_index"],
                "question_id": answer.question_id,
                "option_id": answer.option_id,
                "supplemental_note": answer.supplemental_note,
                "confirmed_at": now,
            }
            for answer in request.answers
        ]
        request_record = {
            "request_id": request.request_id,
            "operation": "save_answers",
            "round_index": current_round["round_index"],
            "revision_before": request.expected_revision,
            "revision_after": request.expected_revision + 1,
            "processed_at": now,
        }
        updated = self._find_one_and_update(
            {
                "diagnosis_id": request.diagnosis_id,
                "visitor_id": visitor_id,
                "revision": request.expected_revision,
                "status": "in_progress",
                "processed_requests.request_id": {"$ne": request.request_id},
                "rounds": {
                    "$elemMatch": {
                        "round_index": current_round["round_index"],
                        "answers": [],
                    }
                },
            },
            {
                "$set": {
                    "rounds.$.answers": answer_records,
                    "rounds.$.answered_at": now,
                    "updated_at": now,
                },
                "$push": {
                    "facts": {"$each": fact_records},
                    "processed_requests": request_record,
                },
                "$inc": {"revision": 1},
            },
        )
        if updated is None:
            session_after_failure = self._get_required_session(request.diagnosis_id, visitor_id)
            duplicate = self._find_processed_request(session_after_failure, request.request_id)
            if duplicate is not None:
                return AnswerSubmissionResult(
                    session=_public_document(session_after_failure),  # type: ignore[arg-type]
                    idempotent=True,
                    request_record=duplicate,
                )
            self._raise_after_failed_write(
                request.diagnosis_id, visitor_id, request.expected_revision
            )

        return AnswerSubmissionResult(
            session=_public_document(updated),  # type: ignore[arg-type]
            idempotent=False,
            request_record=request_record,
        )

    def save_final_result(
        self,
        diagnosis_id: str,
        visitor_id: str,
        decision: DiagnosisAnswerDecision | DiagnosisInsufficientDecision,
        expected_revision: int,
        *,
        execution_request_id: Optional[str] = None,
        result_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Persist a final answer or evidence-insufficient result without auto-resolving it."""
        if not isinstance(decision, (DiagnosisAnswerDecision, DiagnosisInsufficientDecision)):
            raise ValueError("最终结果只能是 answer 或 insufficient 决策")
        session = self._get_required_session(diagnosis_id, visitor_id)
        self._require_expected_revision(session, expected_revision)
        self._require_status(session, "in_progress")

        target_status = (
            "pending_verification" if decision.action == "answer" else "insufficient"
        )
        now = _utc_now()
        query = {
                "diagnosis_id": diagnosis_id,
                "visitor_id": visitor_id,
                "revision": expected_revision,
                "status": "in_progress",
            }
        changes: dict[str, Any] = {
            "$set": {
                    "status": target_status,
                    "result": decision.model_dump(mode="json"),
                    "result_metadata": deepcopy(result_metadata),
                    "updated_at": now,
            },
            "$inc": {"revision": 1},
        }
        if execution_request_id is not None:
            query["execution.request_id"] = execution_request_id
            changes["$set"]["execution"] = None
            changes["$push"] = {
                "processed_requests": self._inference_request_record(
                    execution_request_id, decision.action, expected_revision, now
                )
            }
        updated = self._find_one_and_update(query, changes)
        if updated is None:
            self._raise_after_failed_write(diagnosis_id, visitor_id, expected_revision)
        return _public_document(updated)  # type: ignore[return-value]

    def set_feedback(
        self,
        diagnosis_id: str,
        visitor_id: str,
        feedback_status: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        """Record explicit user resolution feedback from a pending recommendation."""
        if feedback_status not in {"resolved", "unresolved"}:
            raise DiagnosisSessionStateError("反馈状态只能是 resolved 或 unresolved")
        return self._transition_status(
            diagnosis_id,
            visitor_id,
            feedback_status,
            expected_revision,
            feedback={"status": feedback_status, "recorded_at": _utc_now()},
        )

    def transition_status(
        self,
        diagnosis_id: str,
        visitor_id: str,
        target_status: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        """Perform an allowed lifecycle transition (for example, user ending a session)."""
        return self._transition_status(
            diagnosis_id, visitor_id, target_status, expected_revision, feedback=None
        )

    def resume_unresolved(
        self,
        diagnosis_id: str,
        visitor_id: str,
        request_id: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        """Return an unresolved session to inference with retry-safe revision control."""
        session = self._get_required_session(diagnosis_id, visitor_id)
        if self._find_processed_request(session, request_id) is not None:
            return _public_document(session)  # type: ignore[return-value]
        self._require_expected_revision(session, expected_revision)
        if session.get("clarification_count", 0) >= 3:
            raise DiagnosisSessionStateError("已达到三轮追问上限，不能继续诊断")
        self._require_status(session, "unresolved")
        now = _utc_now()
        request_record = {
            "request_id": request_id,
            "operation": "resume_unresolved",
            "revision_before": expected_revision,
            "revision_after": expected_revision + 1,
            "processed_at": now,
        }
        updated = self._find_one_and_update(
            {
                "diagnosis_id": diagnosis_id,
                "visitor_id": visitor_id,
                "revision": expected_revision,
                "status": "unresolved",
                "processed_requests.request_id": {"$ne": request_id},
                "execution": None,
            },
            {
                "$set": {
                    "status": "in_progress",
                    "result": None,
                    "result_metadata": None,
                    "updated_at": now,
                },
                "$push": {"processed_requests": request_record},
                "$inc": {"revision": 1},
            },
        )
        if updated is None:
            latest = self._get_required_session(diagnosis_id, visitor_id)
            if self._find_processed_request(latest, request_id) is not None:
                return _public_document(latest)  # type: ignore[return-value]
            self._raise_after_failed_write(diagnosis_id, visitor_id, expected_revision)
        return _public_document(updated)  # type: ignore[return-value]

    def delete_session(self, diagnosis_id: str, visitor_id: str) -> bool:
        """Delete one visitor-owned session; another visitor's record is untouched."""
        try:
            result = self._collection.delete_one(
                {"diagnosis_id": diagnosis_id, "visitor_id": visitor_id}
            )
            return result.deleted_count == 1
        except Exception as exc:
            raise DiagnosisSessionStorageError("无法删除诊断会话") from exc

    def _transition_status(
        self,
        diagnosis_id: str,
        visitor_id: str,
        target_status: str,
        expected_revision: int,
        feedback: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        session = self._get_required_session(diagnosis_id, visitor_id)
        self._require_expected_revision(session, expected_revision)
        current_status = session["status"]
        if target_status not in _ALLOWED_STATUS_TRANSITIONS.get(current_status, frozenset()):
            raise DiagnosisSessionStateError(
                f"不允许从 {current_status} 转换到 {target_status}"
            )

        now = _utc_now()
        changes: dict[str, Any] = {"status": target_status, "updated_at": now}
        if feedback is not None:
            changes["feedback"] = feedback
        updated = self._find_one_and_update(
            {
                "diagnosis_id": diagnosis_id,
                "visitor_id": visitor_id,
                "revision": expected_revision,
                "status": current_status,
            },
            {"$set": changes, "$inc": {"revision": 1}},
        )
        if updated is None:
            self._raise_after_failed_write(diagnosis_id, visitor_id, expected_revision)
        return _public_document(updated)  # type: ignore[return-value]

    def _find_owned_session(
        self, diagnosis_id: str, visitor_id: str
    ) -> Optional[dict[str, Any]]:
        self._require_nonblank("diagnosis_id", diagnosis_id)
        self._require_nonblank("visitor_id", visitor_id)
        try:
            return self._collection.find_one(
                {"diagnosis_id": diagnosis_id, "visitor_id": visitor_id}
            )
        except Exception as exc:
            raise DiagnosisSessionStorageError("无法读取诊断会话") from exc

    def _get_required_session(self, diagnosis_id: str, visitor_id: str) -> dict[str, Any]:
        session = self._find_owned_session(diagnosis_id, visitor_id)
        if session is None:
            raise DiagnosisSessionNotFoundError("诊断会话不存在或不属于当前访客")
        return session

    def _find_one_and_update(
        self, query: dict[str, Any], update: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        try:
            return self._collection.find_one_and_update(
                query,
                update,
                return_document=ReturnDocument.AFTER,
            )
        except Exception as exc:
            raise DiagnosisSessionStorageError("无法原子更新诊断会话") from exc

    def _raise_after_failed_write(
        self, diagnosis_id: str, visitor_id: str, expected_revision: int
    ) -> None:
        session = self._get_required_session(diagnosis_id, visitor_id)
        if session["revision"] != expected_revision:
            raise DiagnosisSessionConflictError("诊断会话版本已更新，请刷新后重试")
        raise DiagnosisSessionStateError("诊断会话当前状态不允许该操作")

    @staticmethod
    def _find_processed_request(
        session: dict[str, Any], request_id: str
    ) -> Optional[dict[str, Any]]:
        for record in session.get("processed_requests", []):
            if record.get("request_id") == request_id:
                return deepcopy(record)
        return None

    @staticmethod
    def _inference_request_record(
        request_id: str, action: str, revision_before: int, processed_at: datetime
    ) -> dict[str, Any]:
        return {
            "request_id": request_id,
            "operation": "inference",
            "action": action,
            "revision_before": revision_before,
            "revision_after": revision_before + 1,
            "processed_at": processed_at,
        }

    @staticmethod
    def _current_unanswered_round(session: dict[str, Any]) -> Optional[dict[str, Any]]:
        rounds: Iterable[dict[str, Any]] = session.get("rounds", [])
        for round_record in reversed(list(rounds)):
            if not round_record.get("answers"):
                return round_record
        return None

    @staticmethod
    def _validate_answers_for_current_round(
        request: DiagnosisContinueRequest, current_round: dict[str, Any]
    ) -> None:
        """Reject stale question IDs or option IDs before they can alter facts."""
        questions = {question["question_id"]: question for question in current_round["questions"]}
        submitted_question_ids = {answer.question_id for answer in request.answers}
        if submitted_question_ids != set(questions):
            raise DiagnosisSessionStateError("提交答案必须完整对应当前问题组")
        for answer in request.answers:
            option_ids = {option["option_id"] for option in questions[answer.question_id]["options"]}
            if answer.option_id not in option_ids:
                raise DiagnosisSessionStateError("提交的 option_id 不属于对应问题")

    @staticmethod
    def _require_expected_revision(session: dict[str, Any], expected_revision: int) -> None:
        if session["revision"] != expected_revision:
            raise DiagnosisSessionConflictError("诊断会话版本已更新，请刷新后重试")

    @staticmethod
    def _require_status(session: dict[str, Any], expected_status: str) -> None:
        if session["status"] in TERMINAL_STATUSES:
            raise DiagnosisSessionStateError("诊断会话已结束，不能再修改")
        if session["status"] != expected_status:
            raise DiagnosisSessionStateError(
                f"当前状态为 {session['status']}，不能执行该操作"
            )

    @staticmethod
    def _require_nonblank(field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} 不能为空")
