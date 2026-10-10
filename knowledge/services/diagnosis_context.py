"""Deterministic assembly of persisted diagnosis history for shared retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from knowledge.core.devices import resolve_supported_device


DEFAULT_MAX_RETRIEVAL_QUERY_CHARS = 4_000
_UNCERTAIN_OPTION_IDS = frozenset({"unknown", "uncertain", "not_sure", "other"})
_UNCERTAIN_OPTION_TEXTS = frozenset({"不确定", "其他", "不知道", "无法判断"})


@dataclass(frozen=True)
class DiagnosisRetrievalContext:
    """Server-owned diagnosis context ready for the existing retrieval nodes."""

    device_id: str
    device_model: str
    original_problem: str
    confirmed_facts: list[dict[str, Any]]
    answer_history: list[dict[str, Any]]
    rewritten_query: str


class DiagnosisContextAssembler:
    """Turn a persisted session into deterministic retrieval text and facts."""

    def __init__(self, max_retrieval_query_chars: int = DEFAULT_MAX_RETRIEVAL_QUERY_CHARS):
        if max_retrieval_query_chars < 64:
            raise ValueError("max_retrieval_query_chars 必须至少为 64")
        self._max_retrieval_query_chars = max_retrieval_query_chars

    def assemble(self, session: dict[str, Any]) -> DiagnosisRetrievalContext:
        """Assemble only valid, submitted answers; unanswered questions are ignored."""
        device_id = self._require_text(session, "device_id")
        device = resolve_supported_device(device_id)
        original_problem = self._require_text(session, "original_problem")

        answer_history, derived_facts = self._collect_answer_history(session.get("rounds", []))
        confirmed_facts = self._select_persisted_facts(
            session.get("facts"), answer_history, derived_facts
        )
        rewritten_query = self._build_retrieval_query(
            device.device_id,
            device.device_model,
            original_problem,
            confirmed_facts,
            answer_history,
        )
        return DiagnosisRetrievalContext(
            device_id=device.device_id,
            device_model=device.device_model,
            original_problem=original_problem,
            confirmed_facts=confirmed_facts,
            answer_history=answer_history,
            rewritten_query=rewritten_query,
        )

    def _collect_answer_history(
        self, rounds: Any
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not isinstance(rounds, list):
            return [], []

        answer_history: list[dict[str, Any]] = []
        confirmed_facts: list[dict[str, Any]] = []
        seen_answers: set[tuple[Any, str]] = set()
        for round_position, round_record in enumerate(rounds, start=1):
            if not isinstance(round_record, dict):
                continue
            round_index = round_record.get("round_index", round_position)
            question_map = self._question_map(round_record.get("questions"))
            answers = round_record.get("answers")
            if not isinstance(answers, list):
                continue

            for answer in answers:
                if not isinstance(answer, dict):
                    continue
                question_id = answer.get("question_id")
                option_id = answer.get("option_id")
                if not isinstance(question_id, str) or not isinstance(option_id, str):
                    continue
                answer_key = (round_index, question_id)
                if answer_key in seen_answers:
                    continue
                question = question_map.get(question_id)
                if question is None:
                    continue
                option = question["options"].get(option_id)
                if option is None:
                    continue
                seen_answers.add(answer_key)

                supplemental_note = self._clean_text(answer.get("supplemental_note"))
                option_text = option["text"]
                answer_kind = self._answer_kind(option_id, option_text)
                record = {
                    "round_index": round_index,
                    "question_id": question_id,
                    "question": question["text"],
                    "option_id": option_id,
                    "option": option_text,
                    "supplemental_note": supplemental_note,
                    "kind": answer_kind,
                }
                answer_history.append(record)
                if answer_kind == "confirmed":
                    confirmed_facts.append(record)
        return answer_history, confirmed_facts

    @staticmethod
    def _select_persisted_facts(
        persisted_facts: Any,
        answer_history: list[dict[str, Any]],
        derived_facts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Honor saved facts only when they match a valid submitted answer.

        ``facts`` is a denormalized convenience field in MongoDB.  The round
        records remain the source needed to reject malformed or stale entries.
        """
        valid_by_key = {
            (item["round_index"], item["question_id"], item["option_id"]): item
            for item in answer_history
            if item["kind"] == "confirmed"
        }
        selected: list[dict[str, Any]] = []
        selected_keys: set[tuple[Any, str, str]] = set()
        if isinstance(persisted_facts, list):
            for fact in persisted_facts:
                if not isinstance(fact, dict):
                    continue
                key = (fact.get("round_index"), fact.get("question_id"), fact.get("option_id"))
                candidate = valid_by_key.get(key)
                if candidate is not None and key not in selected_keys:
                    selected.append(candidate)
                    selected_keys.add(key)
        for fact in derived_facts:
            key = (fact["round_index"], fact["question_id"], fact["option_id"])
            if key not in selected_keys:
                selected.append(fact)
        return selected

    def _build_retrieval_query(
        self,
        device_id: str,
        device_model: str,
        original_problem: str,
        confirmed_facts: list[dict[str, Any]],
        answer_history: list[dict[str, Any]],
    ) -> str:
        """Prioritize canonical device and original problem within a bounded query."""
        parts = [
            f"设备：{device_model}（device_id={device_id}）",
            f"原始故障描述：{original_problem}",
        ]
        if confirmed_facts:
            parts.append("已确认事实：")
            parts.extend(self._render_answer(fact) for fact in confirmed_facts)

        non_confirmed = [item for item in answer_history if item["kind"] != "confirmed"]
        if non_confirmed:
            parts.append("待确认的历史回答（不可视为已确认事实）：")
            parts.extend(self._render_answer(item) for item in non_confirmed)

        return self._truncate_parts(parts)

    def _truncate_parts(self, parts: list[str]) -> str:
        selected: list[str] = []
        remaining = self._max_retrieval_query_chars
        for part in parts:
            separator_length = 1 if selected else 0
            if len(part) + separator_length <= remaining:
                selected.append(part)
                remaining -= len(part) + separator_length
                continue
            if remaining > separator_length + 1:
                selected.append(part[: remaining - separator_length - 1].rstrip() + "…")
            break
        return "\n".join(selected)

    @staticmethod
    def _question_map(questions: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(questions, list):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for question in questions:
            if not isinstance(question, dict):
                continue
            question_id = question.get("question_id")
            question_text = DiagnosisContextAssembler._clean_text(question.get("text"))
            if not isinstance(question_id, str) or not question_text or question_id in result:
                continue
            options: dict[str, dict[str, str]] = {}
            for option in question.get("options", []):
                if not isinstance(option, dict):
                    continue
                option_id = option.get("option_id")
                option_text = DiagnosisContextAssembler._clean_text(option.get("text"))
                if isinstance(option_id, str) and option_text and option_id not in options:
                    options[option_id] = {"text": option_text}
            if options:
                result[question_id] = {"text": question_text, "options": options}
        return result

    @staticmethod
    def _answer_kind(option_id: str, option_text: str) -> str:
        normalized_id = option_id.strip().lower().replace("-", "_")
        normalized_text = option_text.strip()
        if normalized_id in _UNCERTAIN_OPTION_IDS or normalized_text in _UNCERTAIN_OPTION_TEXTS:
            return "unconfirmed"
        return "confirmed"

    @staticmethod
    def _render_answer(record: dict[str, Any]) -> str:
        line = f"- 第 {record['round_index']} 轮：{record['question']} → {record['option']}"
        if record["supplemental_note"]:
            line += f"；补充：{record['supplemental_note']}"
        return line

    @staticmethod
    def _clean_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(value.split())

    @classmethod
    def _require_text(cls, session: dict[str, Any], field_name: str) -> str:
        value = cls._clean_text(session.get(field_name))
        if not value:
            raise ValueError(f"诊断会话缺少有效字段：{field_name}")
        return value
