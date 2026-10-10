"""LangGraph node that turns a diagnosis candidate into a verified result."""

from __future__ import annotations

from pydantic import TypeAdapter, ValidationError

from knowledge.processor.query_process.base import BaseNode
from knowledge.processor.query_process.state import QueryGraphState
from knowledge.schema.diagnosis_schema import DiagnosisDecision, DiagnosisInsufficientDecision
from knowledge.services.diagnosis_validation import (
    DiagnosisValidationError,
    build_trusted_evidence,
    validate_diagnosis_candidate,
)


_DECISION_ADAPTER = TypeAdapter(DiagnosisDecision)


class DiagnosisValidationNode(BaseNode):
    """Never expose a candidate without validating it against current evidence."""

    name = "diagnosis_validation_node"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        if state.get("diagnosis_status") == "system_error":
            return state
        candidate_payload = state.get("diagnosis_candidate")
        if not isinstance(candidate_payload, dict) or not candidate_payload:
            return self._set_system_error(state, "missing_candidate")

        try:
            candidate = _DECISION_ADAPTER.validate_python(candidate_payload)
            trusted_evidence = build_trusted_evidence(
                state.get("reranked_docs"), state.get("device_id")
            )
            validated = validate_diagnosis_candidate(candidate, trusted_evidence)
        except (DiagnosisValidationError, ValidationError) as exc:
            code = exc.code if isinstance(exc, DiagnosisValidationError) else "invalid_candidate"
            return self._set_rejected(state, code)
        except Exception as exc:
            self.logger.exception("诊断证据校验异常: %s", exc)
            return self._set_system_error(state, "validation_unavailable")
        return self._set_validated(state, validated)

    @staticmethod
    def _set_validated(state: QueryGraphState, decision: DiagnosisDecision) -> QueryGraphState:
        state["answer"] = ""
        state["diagnosis_validated"] = decision.model_dump(mode="json")
        state["diagnosis_validation_passed"] = True
        state["diagnosis_validation_error"] = {}
        state["diagnosis_system_error"] = {}
        state["diagnosis_status"] = "validated"
        state["diagnosis_message"] = "诊断结果已通过本轮本地证据与安全校验"
        return state

    @staticmethod
    def _set_rejected(state: QueryGraphState, code: str) -> QueryGraphState:
        fallback = DiagnosisInsufficientDecision(
            action="insufficient",
            reason="候选诊断未能通过本轮本地证据或安全校验，无法可靠提供操作建议。",
            next_steps=["请停止进一步拆卸或带电操作，并补充可核对的 K1 本地资料或联系官方支持。"],
        )
        state["answer"] = ""
        state["diagnosis_validated"] = fallback.model_dump(mode="json")
        state["diagnosis_validation_passed"] = False
        state["diagnosis_validation_error"] = {"code": code}
        state["diagnosis_system_error"] = {}
        state["diagnosis_status"] = "validation_rejected"
        state["diagnosis_message"] = "候选诊断未通过证据或安全校验，已安全降级"
        return state

    @staticmethod
    def _set_system_error(state: QueryGraphState, code: str) -> QueryGraphState:
        state["answer"] = ""
        state["diagnosis_validated"] = {}
        state["diagnosis_validation_passed"] = False
        state["diagnosis_validation_error"] = {}
        state["diagnosis_system_error"] = {
            "code": code,
            "message": "诊断证据校验暂时不可用，请稍后重试。",
        }
        state["diagnosis_status"] = "system_error"
        state["diagnosis_message"] = state["diagnosis_system_error"]["message"]
        return state
