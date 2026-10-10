"""Evidence-bounded, internal LLM decision node for diagnosis mode.

The node returns a *candidate* only.  It deliberately does not save rounds or
final results: T2-05 must first verify citations and recommendation support.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import TypeAdapter, ValidationError

from knowledge.processor.query_process.base import BaseNode
from knowledge.processor.query_process.state import QueryGraphState
from knowledge.prompt.diagnosis_prompt import (
    DIAGNOSIS_DECISION_SYSTEM_PROMPT,
    DIAGNOSIS_DECISION_USER_TEMPLATE,
)
from knowledge.schema.diagnosis_schema import (
    DiagnosisAskDecision,
    DiagnosisDecision,
    DiagnosisInsufficientDecision,
)
from knowledge.utils.client.ai_clients import AIClients


MAX_CLARIFICATION_ROUNDS = 3
DEFAULT_MAX_ATTEMPTS = 2
_DECISION_ADAPTER = TypeAdapter(DiagnosisDecision)


class DiagnosisDecisionNode(BaseNode):
    """Turn reranked local K1 evidence into a schema-checked candidate."""

    name = "diagnosis_decision_node"

    def __init__(self, max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        super().__init__()
        if max_attempts < 1:
            raise ValueError("max_attempts 必须至少为 1")
        self._max_attempts = max_attempts

    def process(self, state: QueryGraphState) -> QueryGraphState:
        """Generate a non-persistent candidate or expose a system failure."""
        evidence = self._trusted_local_evidence(state)
        if not evidence:
            return self._set_candidate(state, self._no_evidence_decision())

        clarification_count = self._clarification_count(state)
        prompt = self._build_prompt(state, evidence, clarification_count)
        state["prompt"] = prompt
        attempted_errors: list[str] = []
        model_failure = False

        for _ in range(self._max_attempts):
            try:
                decision = self._invoke_and_parse(prompt)
                self._validate_candidate(decision, state, clarification_count)
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                attempted_errors.append(str(exc))
                continue
            except Exception as exc:  # LLM transport/timeout/client failures
                self.logger.warning("诊断候选模型调用失败: %s", exc)
                attempted_errors.append(str(exc))
                model_failure = True
                continue
            return self._set_candidate(state, decision)

        self.logger.warning("诊断候选在有限重试后仍无效: %s", attempted_errors)
        if clarification_count >= MAX_CLARIFICATION_ROUNDS and any(
            "三轮追问上限" in error for error in attempted_errors
        ):
            return self._set_candidate(state, self._round_limit_decision())
        if model_failure:
            return self._set_system_error(state, "model_unavailable")
        return self._set_system_error(state, "invalid_model_output")

    def _invoke_and_parse(self, prompt: str) -> DiagnosisDecision:
        llm_client = AIClients.get_llm_openai(response_format=True)
        if llm_client is None:
            raise RuntimeError("LLM 客户端不可用")
        response = llm_client.invoke(
            [
                SystemMessage(content=DIAGNOSIS_DECISION_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        content = getattr(response, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("模型未返回 JSON 文本")
        return _DECISION_ADAPTER.validate_python(json.loads(content))

    def _validate_candidate(
        self,
        decision: DiagnosisDecision,
        state: QueryGraphState,
        clarification_count: int,
    ) -> None:
        if isinstance(decision, DiagnosisAskDecision):
            if clarification_count >= MAX_CLARIFICATION_ROUNDS:
                raise ValueError("已达到三轮追问上限，不能再返回 ask")
            historical_questions = {
                self._normalize_question(item.get("question"))
                for item in state.get("diagnosis_answer_history", [])
                if isinstance(item, dict) and item.get("question")
            }
            candidate_questions = {
                self._normalize_question(question.text) for question in decision.questions
            }
            if "" in candidate_questions or historical_questions.intersection(candidate_questions):
                raise ValueError("候选问题重复已回答的问题")

    @staticmethod
    def _trusted_local_evidence(state: QueryGraphState) -> list[dict[str, str]]:
        """Defensively discard web, cross-device and unidentifiable records."""
        device_id = state.get("device_id")
        evidence: list[dict[str, str]] = []
        for document in state.get("reranked_docs", []) or []:
            if not isinstance(document, dict):
                continue
            if document.get("source_type") != "local" or document.get("device_id") != device_id:
                continue
            source_id = document.get("source_id")
            content = document.get("content")
            if not isinstance(source_id, str) or not source_id.strip():
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            title = document.get("title") or document.get("file_title") or "未命名本地资料"
            evidence.append(
                {
                    "source_id": source_id.strip(),
                    "title": str(title).strip(),
                    "content": content.strip(),
                }
            )
        return evidence

    def _build_prompt(
        self,
        state: QueryGraphState,
        evidence: list[dict[str, str]],
        clarification_count: int,
    ) -> str:
        rendered_evidence = []
        remaining = self.config.max_context_chars
        for document in evidence:
            entry = json.dumps(document, ensure_ascii=False)
            if len(entry) > remaining:
                entry = entry[:remaining].rstrip() + "…"
            if not entry:
                break
            rendered_evidence.append(entry)
            remaining -= len(entry)
            if remaining <= 0:
                break
        return DIAGNOSIS_DECISION_USER_TEMPLATE.format(
            device_id=state.get("device_id", ""),
            device_model=state.get("device_model", ""),
            original_problem=state.get("original_query", ""),
            confirmed_facts=json.dumps(state.get("diagnosis_facts", []), ensure_ascii=False),
            answer_history=json.dumps(state.get("diagnosis_answer_history", []), ensure_ascii=False),
            clarification_count=clarification_count,
            can_ask="否" if clarification_count >= MAX_CLARIFICATION_ROUNDS else "是",
            evidence="\n".join(rendered_evidence),
        )

    @staticmethod
    def _clarification_count(state: QueryGraphState) -> int:
        count = state.get("clarification_count", 0)
        return count if isinstance(count, int) and count >= 0 else 0

    @staticmethod
    def _normalize_question(value: Any) -> str:
        return "".join(str(value).split()).casefold() if isinstance(value, str) else ""

    @staticmethod
    def _no_evidence_decision() -> DiagnosisInsufficientDecision:
        return DiagnosisInsufficientDecision(
            action="insufficient",
            reason="当前没有可用的 Creality K1 本地检索证据，无法可靠给出诊断。",
            next_steps=["请补充已核对归属 Creality K1 的资料后再试，或联系官方支持。"],
        )

    @staticmethod
    def _round_limit_decision() -> DiagnosisInsufficientDecision:
        return DiagnosisInsufficientDecision(
            action="insufficient",
            reason="已达到三轮澄清上限，现有资料不足以形成符合约束的可靠结论。",
            next_steps=["请根据现有回答整理现象并联系官方支持，或补充可核对的 K1 资料。"],
        )

    @staticmethod
    def _set_candidate(state: QueryGraphState, decision: DiagnosisDecision) -> QueryGraphState:
        state["answer"] = ""
        state["diagnosis_candidate"] = decision.model_dump(mode="json")
        state["diagnosis_system_error"] = {}
        state["diagnosis_status"] = "candidate"
        state["diagnosis_message"] = "候选诊断决策尚待证据校验"
        return state

    @staticmethod
    def _set_system_error(state: QueryGraphState, code: str) -> QueryGraphState:
        state["answer"] = ""
        state["diagnosis_candidate"] = {}
        state["diagnosis_system_error"] = {
            "code": code,
            "message": "诊断模型暂时不可用或返回无效结构，请稍后重试。",
        }
        state["diagnosis_status"] = "system_error"
        state["diagnosis_message"] = state["diagnosis_system_error"]["message"]
        return state
