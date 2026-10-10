import copy
import unittest
from unittest.mock import patch

from knowledge.processor.query_process.nodes.diagnosis_validation import DiagnosisValidationNode
from knowledge.services.diagnosis_validation import build_trusted_evidence


K1_CONTENT = "首层粘附异常时，请检查首层调平设置。关闭电源并等待设备冷却后，才可拆卸底板检查线束。"
K1_DOCUMENT = {
    "source": "local",
    "source_type": "local",
    "source_id": "chunk:101",
    "chunk_id": 101,
    "device_id": "creality-k1",
    "device_model": "Creality K1",
    "item_name": "Creality K1",
    "title": "Creality K1 用户手册",
    "content": K1_CONTENT,
}
QUESTION_EXCERPT = "首层粘附异常时，请检查首层调平设置。"


def evidence_excerpt(support_text="首层粘附异常", excerpt=QUESTION_EXCERPT):
    return {
        "source_id": "chunk:101",
        "excerpt": excerpt,
        "support_text": support_text,
    }


def ask_candidate():
    return {
        "action": "ask",
        "questions": [{
            "question_id": "first-layer",
            "text": "首层粘附异常是否只发生在首层？",
            "options": [
                {"option_id": "yes", "text": "是", "option_type": "normal"},
                {"option_id": "unknown", "text": "不确定", "option_type": "uncertain"},
            ],
            "references": [evidence_excerpt()],
        }],
    }


def answer_candidate(text="请检查首层调平设置。", evidence=None):
    return {
        "action": "answer",
        "conclusion": "资料指向首层调平设置需要检查。",
        "recommendations": [{
            "text": text,
            "evidence": evidence or [evidence_excerpt("检查首层调平设置")],
        }],
        "references": [{"source_id": "chunk:101"}],
        "safety_notes": ["接触热端前先等待设备冷却。"],
    }


class DiagnosisValidationTestCase(unittest.TestCase):
    @staticmethod
    def _state(candidate, docs=None, **overrides):
        state = {
            "mode": "diagnosis",
            "device_id": "creality-k1",
            "reranked_docs": docs if docs is not None else [copy.deepcopy(K1_DOCUMENT)],
            "diagnosis_candidate": candidate,
            "diagnosis_status": "candidate",
            "diagnosis_system_error": {},
        }
        state.update(overrides)
        return state

    def test_valid_k1_local_document_and_citations_pass(self):
        trusted = build_trusted_evidence([K1_DOCUMENT], "creality-k1")
        result = DiagnosisValidationNode().process(self._state(answer_candidate()))

        self.assertEqual([item.source_id for item in trusted], ["chunk:101"])
        self.assertEqual(result["diagnosis_status"], "validated")
        self.assertTrue(result["diagnosis_validation_passed"])
        self.assertEqual(result["diagnosis_validated"]["action"], "answer")

    def test_forged_chunk_source_web_cross_device_and_missing_metadata_are_excluded(self):
        forged = {**K1_DOCUMENT, "source_id": "chunk:forged"}
        web = {**K1_DOCUMENT, "source": "web", "source_type": "web"}
        other_device = {**K1_DOCUMENT, "device_id": "other-device"}
        missing_chunk = {key: value for key, value in K1_DOCUMENT.items() if key != "chunk_id"}
        conflicting_item = {**K1_DOCUMENT, "item_name": "Creality K1 Max"}

        trusted = build_trusted_evidence(
            [forged, web, other_device, missing_chunk, conflicting_item], "creality-k1"
        )
        result = DiagnosisValidationNode().process(self._state(ask_candidate(), [forged]))

        self.assertEqual(trusted, [])
        self.assertEqual(result["diagnosis_status"], "validation_rejected")
        self.assertEqual(result["diagnosis_validation_error"]["code"], "invalid_reference")
        self.assertEqual(result["diagnosis_validated"]["action"], "insufficient")

    def test_one_invalid_question_reference_rejects_entire_ask_group(self):
        candidate = ask_candidate()
        candidate["questions"].append({
            "question_id": "second",
            "text": "首层粘附异常是否持续出现？",
            "options": [
                {"option_id": "yes", "text": "是", "option_type": "normal"},
                {"option_id": "no", "text": "否", "option_type": "normal"},
            ],
            "references": [{
                "source_id": "chunk:missing",
                "excerpt": QUESTION_EXCERPT,
                "support_text": "首层粘附异常",
            }],
        })

        result = DiagnosisValidationNode().process(self._state(candidate))

        self.assertEqual(result["diagnosis_status"], "validation_rejected")
        self.assertEqual(result["diagnosis_validation_error"]["code"], "invalid_reference")

    def test_real_source_does_not_allow_unsupported_recommendation(self):
        candidate = answer_candidate("请清洁喷嘴。")

        result = DiagnosisValidationNode().process(self._state(candidate))

        self.assertEqual(result["diagnosis_status"], "validation_rejected")
        self.assertEqual(result["diagnosis_validation_error"]["code"], "unsupported_content")

    def test_high_risk_operation_without_documented_safety_boundary_is_blocked(self):
        candidate = answer_candidate(
            "请拆卸底板检查首层调平设置。",
            [evidence_excerpt("首层调平设置")],
        )

        result = DiagnosisValidationNode().process(self._state(candidate))

        self.assertEqual(result["diagnosis_status"], "validation_rejected")
        self.assertEqual(result["diagnosis_validation_error"]["code"], "unsafe_operation")

    def test_insufficient_without_evidence_is_valid_but_repair_step_is_not(self):
        safe = {
            "action": "insufficient",
            "reason": "本轮没有可用 K1 本地资料。",
            "next_steps": ["停止尝试并联系官方支持。"],
        }
        unsafe = {
            "action": "insufficient",
            "reason": "资料不足。",
            "next_steps": ["请拆卸底板检查线束。"],
        }
        unsupported = {
            "action": "insufficient",
            "reason": "资料不足。",
            "next_steps": ["请调整首层调平设置。"],
        }

        safe_result = DiagnosisValidationNode().process(self._state(safe, []))
        unsafe_result = DiagnosisValidationNode().process(self._state(unsafe, []))
        unsupported_result = DiagnosisValidationNode().process(self._state(unsupported, []))

        self.assertEqual(safe_result["diagnosis_status"], "validated")
        self.assertEqual(unsafe_result["diagnosis_status"], "validation_rejected")
        self.assertEqual(unsafe_result["diagnosis_validation_error"]["code"], "unsafe_insufficient")
        self.assertEqual(unsupported_result["diagnosis_validation_error"]["code"], "unsupported_insufficient")

    def test_validation_exception_and_existing_model_failure_stay_system_errors(self):
        with patch(
            "knowledge.processor.query_process.nodes.diagnosis_validation.build_trusted_evidence",
            side_effect=RuntimeError("storage unavailable"),
        ):
            failed_validation = DiagnosisValidationNode().process(self._state(answer_candidate()))
        existing_model_failure = DiagnosisValidationNode().process(
            self._state({}, diagnosis_status="system_error", diagnosis_system_error={"code": "model_unavailable"})
        )

        self.assertEqual(failed_validation["diagnosis_status"], "system_error")
        self.assertEqual(failed_validation["diagnosis_system_error"]["code"], "validation_unavailable")
        self.assertEqual(existing_model_failure["diagnosis_system_error"]["code"], "model_unavailable")


if __name__ == "__main__":
    unittest.main()
