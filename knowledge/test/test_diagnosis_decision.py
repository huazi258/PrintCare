import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from knowledge.processor.query_process.nodes.diagnosis_decision import DiagnosisDecisionNode


class FakeLlm:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, str):
            return SimpleNamespace(content=response)
        return SimpleNamespace(content=json.dumps(response, ensure_ascii=False))


class CallbackLlm:
    def __init__(self):
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages)
        prompt = messages[-1].content
        if "热床已经清洁" in prompt:
            payload = {
                "action": "answer",
                "conclusion": "资料与已确认的清洁情况支持继续检查首层调平。",
                "recommendations": [{
                    "text": "按资料检查首层调平设置。",
                    "evidence": [{
                        "source_id": "chunk:101",
                        "excerpt": "首层粘附异常时，可检查打印平台清洁和首层调平设置。",
                        "support_text": "首层调平设置",
                    }],
                }],
                "references": [{"source_id": "chunk:101"}],
                "safety_notes": ["接触热端前先等待冷却。"],
            }
        else:
            payload = ask_payload()
        return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))


def ask_payload(question="首层粘附异常是否只发生在首层？"):
    return {
        "action": "ask",
        "questions": [
            {
                "question_id": "first-layer-stage",
                "text": question,
                "options": [
                    {"option_id": "yes", "text": "是，仅首层", "option_type": "normal"},
                    {"option_id": "unknown", "text": "不确定", "option_type": "uncertain"},
                ],
                "references": [{
                    "source_id": "chunk:101",
                    "excerpt": "首层粘附异常时，可检查打印平台清洁和首层调平设置。",
                    "support_text": "首层粘附异常",
                }],
            }
        ],
    }


def answer_payload():
    return {
        "action": "answer",
        "conclusion": "资料指向需要检查首层调平。",
        "recommendations": [{
            "text": "根据 K1 本地资料检查首层调平设置。",
            "evidence": [{
                "source_id": "chunk:101",
                "excerpt": "首层粘附异常时，可检查打印平台清洁和首层调平设置。",
                "support_text": "首层调平设置",
            }],
        }],
        "references": [{"source_id": "chunk:101"}],
        "safety_notes": ["热端冷却后再进行接触式检查。"],
    }


class DiagnosisDecisionNodeTestCase(unittest.TestCase):
    @staticmethod
    def _state(**overrides):
        state = {
            "mode": "diagnosis",
            "device_id": "creality-k1",
            "device_model": "Creality K1",
            "original_query": "首层无法粘附打印平台",
            "diagnosis_facts": [],
            "diagnosis_answer_history": [],
            "clarification_count": 0,
            "reranked_docs": [
                {
                    "source": "local",
                    "source_type": "local",
                    "source_id": "chunk:101",
                    "chunk_id": 101,
                    "device_id": "creality-k1",
                    "title": "Creality K1 用户手册",
                    "content": "首层粘附异常时，可检查打印平台清洁和首层调平设置。",
                }
            ],
        }
        state.update(overrides)
        return state

    def test_local_k1_evidence_generates_a_schema_valid_ask_candidate(self):
        llm = FakeLlm([ask_payload()])
        with patch(
            "knowledge.processor.query_process.nodes.diagnosis_decision.AIClients.get_llm_openai",
            return_value=llm,
        ):
            result = DiagnosisDecisionNode().process(self._state())

        self.assertEqual(result["diagnosis_status"], "candidate")
        self.assertEqual(result["diagnosis_candidate"]["action"], "ask")
        self.assertEqual(
            result["diagnosis_candidate"]["questions"][0]["options"][1]["option_type"],
            "uncertain",
        )
        self.assertIn("chunk:101", llm.prompts[0][-1].content)
        self.assertEqual(result["answer"], "")

    def test_history_changes_the_model_input_and_candidate_decision(self):
        llm = CallbackLlm()
        with patch(
            "knowledge.processor.query_process.nodes.diagnosis_decision.AIClients.get_llm_openai",
            return_value=llm,
        ):
            first = DiagnosisDecisionNode().process(self._state())
            later = DiagnosisDecisionNode().process(
                self._state(
                    diagnosis_facts=[{"question": "平台是否已经清洁", "option": "热床已经清洁"}],
                    diagnosis_answer_history=[
                        {
                            "question": "平台是否已经清洁",
                            "option": "热床已经清洁",
                            "kind": "confirmed",
                        }
                    ],
                    clarification_count=1,
                )
            )

        self.assertEqual(first["diagnosis_candidate"]["action"], "ask")
        self.assertEqual(later["diagnosis_candidate"]["action"], "answer")
        self.assertNotEqual(llm.prompts[0][-1].content, llm.prompts[1][-1].content)

    def test_no_trusted_local_k1_evidence_returns_insufficient_without_model_call(self):
        with patch(
            "knowledge.processor.query_process.nodes.diagnosis_decision.AIClients.get_llm_openai"
        ) as get_llm:
            result = DiagnosisDecisionNode().process(
                self._state(
                    reranked_docs=[
                        {"source_type": "web", "source_id": "https://example.test", "content": "网页"},
                        {
                            "source_type": "local",
                            "source_id": "chunk:other-device",
                            "device_id": "other-device",
                            "content": "其他设备资料",
                        },
                    ]
                )
            )

        get_llm.assert_not_called()
        self.assertEqual(result["diagnosis_candidate"]["action"], "insufficient")

    def test_repeated_answered_question_is_retried_before_accepting_a_new_decision(self):
        llm = FakeLlm([ask_payload("喷嘴是否已经清洁？"), answer_payload()])
        with patch(
            "knowledge.processor.query_process.nodes.diagnosis_decision.AIClients.get_llm_openai",
            return_value=llm,
        ):
            result = DiagnosisDecisionNode().process(
                self._state(
                    diagnosis_answer_history=[
                        {"question": "喷嘴是否已经清洁？", "option": "是", "kind": "confirmed"}
                    ]
                )
            )

        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(result["diagnosis_candidate"]["action"], "answer")

    def test_round_limit_converts_repeated_ask_to_safe_insufficient_candidate(self):
        llm = FakeLlm([ask_payload(), ask_payload()])
        with patch(
            "knowledge.processor.query_process.nodes.diagnosis_decision.AIClients.get_llm_openai",
            return_value=llm,
        ):
            result = DiagnosisDecisionNode().process(self._state(clarification_count=3))

        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(result["diagnosis_candidate"]["action"], "insufficient")
        self.assertIn("三轮", result["diagnosis_candidate"]["reason"])

    def test_invalid_json_and_timeout_become_system_errors_after_bounded_retries(self):
        malformed = FakeLlm(["not json", {"action": "ask", "questions": []}])
        with patch(
            "knowledge.processor.query_process.nodes.diagnosis_decision.AIClients.get_llm_openai",
            return_value=malformed,
        ):
            malformed_result = DiagnosisDecisionNode().process(self._state())

        timeout = FakeLlm([TimeoutError("timeout"), TimeoutError("timeout")])
        with patch(
            "knowledge.processor.query_process.nodes.diagnosis_decision.AIClients.get_llm_openai",
            return_value=timeout,
        ):
            timeout_result = DiagnosisDecisionNode().process(self._state())

        self.assertEqual(len(malformed.prompts), 2)
        self.assertEqual(malformed_result["diagnosis_status"], "system_error")
        self.assertEqual(malformed_result["diagnosis_system_error"]["code"], "invalid_model_output")
        self.assertEqual(len(timeout.prompts), 2)
        self.assertEqual(timeout_result["diagnosis_system_error"]["code"], "model_unavailable")
        self.assertEqual(timeout_result["diagnosis_candidate"], {})


if __name__ == "__main__":
    unittest.main()
