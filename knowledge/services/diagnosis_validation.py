"""Deterministic evidence and safety checks for diagnosis candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from knowledge.core.devices import resolve_supported_device
from knowledge.schema.diagnosis_schema import (
    DiagnosisAnswerDecision,
    DiagnosisAskDecision,
    DiagnosisDecision,
    DiagnosisInsufficientDecision,
    EvidenceExcerpt,
)


@dataclass(frozen=True)
class TrustedEvidence:
    """A retriever document eligible for diagnosis citation in this run."""

    source_id: str
    chunk_id: str
    title: str
    content: str


class DiagnosisValidationError(ValueError):
    """A candidate is structurally valid but not safe or evidence-backed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


_RISK_CATEGORIES = {
    "disassembly": (
        ("拆机", "拆卸", "拆开", "拆底板", "拆外壳", "拆壳", "拆盖", "开盖", "打开底板", "打开外壳", "打开机箱", "disassemble", "remove cover"),
        ("断电", "关闭电源", "拔掉电源", "power off", "unplug"),
    ),
    "electrical": (
        ("带电", "通电", "电源", "电气", "线路", "线束", "接线", "端子", "主板", "裸露导线", "短路", "电击", "高压", "市电", "live", "energized", "power supply", "electrical", "wiring", "mainboard"),
        ("断电", "关闭电源", "拔掉电源", "power off", "unplug"),
    ),
    "thermal": (
        ("热端", "喷嘴", "喷头", "热床", "高温", "加热", "加热器", "加热棒", "hotend", "nozzle", "heater bed", "heater", "high temperature"),
        ("等待冷却", "完全冷却", "冷却后", "低于", "降温", "cool down", "cooled down", "temperature below"),
    ),
    "replacement": (
        ("更换", "焊接", "replace", "solder"),
        ("断电", "关闭电源", "拔掉电源", "等待冷却", "完全冷却", "power off", "unplug", "cool down", "cooled down"),
    ),
}
_REPAIR_OPERATION_MARKERS = (
    "检查", "清洁", "调整", "校准", "设置", "更换", "拆", "维修", "修复", "安装", "加热",
    "inspect", "clean", "adjust", "calibrate", "replace", "repair", "install", "heat",
)
_GENERIC_SUPPORT_TERMS = (
    "检查", "设备", "打印机", "机器", "操作", "异常", "问题", "情况", "建议", "相关", "进行", "用户", "请", "需要", "可以",
    "check", "device", "printer", "machine", "operation", "issue", "problem", "please", "should",
)


def build_trusted_evidence(
    reranked_docs: Any, device_id: Any
) -> list[TrustedEvidence]:
    """Return only internally consistent local documents for the target device."""
    try:
        device = resolve_supported_device(device_id)
    except Exception:
        return []
    if not isinstance(reranked_docs, list):
        return []

    trusted: dict[str, TrustedEvidence] = {}
    rejected_duplicates: set[str] = set()
    for document in reranked_docs:
        if not isinstance(document, dict):
            continue
        if document.get("source") != "local" or document.get("source_type") != "local":
            continue
        if document.get("device_id") != device.device_id:
            continue
        if _conflicts_with_device(document.get("device_model"), device.device_model):
            continue
        if _conflicts_with_device(document.get("item_name"), device.item_name):
            continue

        chunk_id = document.get("chunk_id")
        source_id = _clean_text(document.get("source_id"))
        content = _clean_text(document.get("content"))
        if chunk_id is None or not str(chunk_id).strip() or not source_id or not content:
            continue
        normalized_chunk_id = str(chunk_id).strip()
        if source_id != f"chunk:{normalized_chunk_id}":
            continue

        title = _clean_text(document.get("title")) or _clean_text(document.get("file_title"))
        candidate = TrustedEvidence(source_id, normalized_chunk_id, title, content)
        existing = trusted.get(source_id)
        if existing is not None and existing != candidate:
            rejected_duplicates.add(source_id)
            trusted.pop(source_id, None)
            continue
        if source_id not in rejected_duplicates:
            trusted[source_id] = candidate
    return list(trusted.values())


def validate_diagnosis_candidate(
    candidate: DiagnosisDecision,
    trusted_evidence: list[TrustedEvidence],
) -> DiagnosisDecision:
    """Validate source identity, declared excerpts, support text, and safety."""
    evidence_by_source = {item.source_id: item for item in trusted_evidence}
    if isinstance(candidate, DiagnosisAskDecision):
        for question in candidate.questions:
            _validate_evidence_links(question.references, question.text, evidence_by_source)
        return candidate
    if isinstance(candidate, DiagnosisAnswerDecision):
        if not evidence_by_source:
            raise DiagnosisValidationError("no_trusted_evidence", "没有可验证的本地 K1 证据")
        global_sources = {reference.source_id for reference in candidate.references}
        if not global_sources or not global_sources.issubset(evidence_by_source):
            raise DiagnosisValidationError("invalid_reference", "诊断结论包含未命中的来源标识")
        _validate_evidence_links(candidate.conclusion_evidence, candidate.conclusion, evidence_by_source)
        if not {item.source_id for item in candidate.conclusion_evidence}.issubset(global_sources):
            raise DiagnosisValidationError("unlinked_conclusion", "结论证据未列入结论引用")
        for recommendation in candidate.recommendations:
            _validate_evidence_links(recommendation.evidence, recommendation.text, evidence_by_source)
            if not {item.source_id for item in recommendation.evidence}.issubset(global_sources):
                raise DiagnosisValidationError("unlinked_recommendation", "建议证据未列入结论引用")
            _validate_risky_recommendation(recommendation.text, recommendation.evidence)
        return candidate
    if isinstance(candidate, DiagnosisInsufficientDecision):
        if any(_is_risky_operation(step) for step in candidate.next_steps):
            raise DiagnosisValidationError("unsafe_insufficient", "资料不足结果不能夹带高风险维修操作")
        if any(_is_repair_operation(step) for step in candidate.next_steps):
            raise DiagnosisValidationError("unsupported_insufficient", "资料不足结果不能夹带无依据的维修操作")
        return candidate
    raise DiagnosisValidationError("unknown_action", "未知诊断候选类型")


def _validate_evidence_links(
    references: list[EvidenceExcerpt], subject: str, evidence_by_source: dict[str, TrustedEvidence]
) -> None:
    if not references:
        raise DiagnosisValidationError("missing_reference", "缺少可核验的来源")
    normalized_subject = _normalise(subject)
    for reference in references:
        evidence = evidence_by_source.get(reference.source_id)
        if evidence is None:
            raise DiagnosisValidationError("invalid_reference", "引用不属于本轮可信证据")
        if reference.excerpt not in evidence.content:
            raise DiagnosisValidationError("invalid_excerpt", "声明的原文片段不在引用文档中")
        normalized_support = _normalise(reference.support_text)
        if len(normalized_support) < 3:
            raise DiagnosisValidationError("weak_support", "支持片段过短，不能建立可追溯关系")
        if _is_generic_support(normalized_support):
            raise DiagnosisValidationError("weak_support", "支持片段过于通用，不能建立可追溯关系")
        if normalized_support not in _normalise(reference.excerpt):
            raise DiagnosisValidationError("invalid_support", "支持片段不在声明的原文片段中")
        if normalized_support not in normalized_subject:
            raise DiagnosisValidationError("unsupported_content", "建议或问题未包含资料支持片段")


def _conflicts_with_device(value: Any, expected: str) -> bool:
    cleaned = _clean_text(value)
    return bool(cleaned) and cleaned != expected


def _validate_risky_recommendation(text: str, evidence: list[EvidenceExcerpt]) -> None:
    normalized_text = _normalise(text)
    for operation_markers, safety_markers in _RISK_CATEGORIES.values():
        matched_markers = [marker for marker in operation_markers if marker.casefold() in normalized_text]
        if not matched_markers:
            continue
        if not any(
            any(marker.casefold() in _normalise(item.support_text) for marker in matched_markers)
            and _has_operation_safety_pair(item.excerpt, matched_markers, safety_markers)
            for item in evidence
        ):
            raise DiagnosisValidationError(
                "unsafe_operation",
                "高风险操作缺少同一原文片段中的具体操作依据和适用安全条件",
            )


def _has_operation_safety_pair(
    excerpt: str,
    operation_markers: list[str],
    safety_markers: tuple[str, ...],
) -> bool:
    for segment in re.split(r"[。！？!?；;\r\n]+", excerpt):
        normalized_segment = _normalise(segment)
        if (
            any(marker.casefold() in normalized_segment for marker in operation_markers)
            and any(marker.casefold() in normalized_segment for marker in safety_markers)
        ):
            return True
    return False


def _is_risky_operation(text: str) -> bool:
    normalized = _normalise(text)
    return any(
        any(marker.casefold() in normalized for marker in operation_markers)
        for operation_markers, _ in _RISK_CATEGORIES.values()
    )


def _is_repair_operation(text: str) -> bool:
    normalized = _normalise(text)
    return any(marker.casefold() in normalized for marker in _REPAIR_OPERATION_MARKERS)


def _is_generic_support(normalized_support: str) -> bool:
    remainder = normalized_support
    for term in _GENERIC_SUPPORT_TERMS:
        remainder = remainder.replace(term.casefold(), "")
    return len(remainder) < 2


def _normalise(value: str) -> str:
    return "".join(value.split()).casefold()


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
