import unittest

from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from knowledge.api.query_router import create_app
from knowledge.schema.diagnosis_schema import (
    DiagnosisAnswerDecision,
    DiagnosisAskDecision,
    DiagnosisContinueRequest,
    DiagnosisDecision,
    DiagnosisInsufficientDecision,
    DiagnosisResponse,
    DiagnosisStartRequest,
)
from knowledge.schema.query_schema import QueryRequest


class DiagnosisSchemaTestCase(unittest.TestCase):
    @staticmethod
    def _reference(source_id="chunk:101"):
        return {"source_id": source_id}

    @classmethod
    def _evidence_excerpt(cls, source_id="chunk:101"):
        return {
            "source_id": source_id,
            "excerpt": "首层调平设置需要检查。",
            "support_text": "首层调平设置",
        }

    @classmethod
    def _question(cls, question_id="question-1", option_count=2):
        return {
            "question_id": question_id,
            "text": "异常在什么时候发生？",
            "options": [
                {"option_id": f"option-{index}", "text": f"选项 {index}"}
                for index in range(1, option_count + 1)
            ],
            "references": [cls._evidence_excerpt()],
        }

    @classmethod
    def _ask(cls, question_count=1, option_count=2):
        return {
            "action": "ask",
            "questions": [
                cls._question(question_id=f"question-{index}", option_count=option_count)
                for index in range(1, question_count + 1)
            ],
        }

    @classmethod
    def _answer(cls):
        return {
            "action": "answer",
            "conclusion": "现有资料指向首层调平设置需要检查。",
            "conclusion_evidence": [cls._evidence_excerpt()],
            "recommendations": [{
                "text": "根据设备手册检查首层调平设置。",
                "evidence": [cls._evidence_excerpt()],
            }],
            "references": [cls._reference()],
            "safety_notes": ["等待热端冷却后再进行需要接触热端的检查。"],
        }

    @staticmethod
    def _insufficient():
        return {
            "action": "insufficient",
            "reason": "本轮命中的本地资料未覆盖该异常现象。",
            "confirmed_facts": ["用户报告首层粘附异常。"],
            "next_steps": ["请补充故障发生阶段，或联系官方支持。"],
        }

    def test_three_legal_decisions_parse_through_discriminated_union(self):
        adapter = TypeAdapter(DiagnosisDecision)

        self.assertIsInstance(adapter.validate_python(self._ask()), DiagnosisAskDecision)
        self.assertIsInstance(adapter.validate_python(self._answer()), DiagnosisAnswerDecision)
        self.assertIsInstance(
            adapter.validate_python(self._insufficient()), DiagnosisInsufficientDecision
        )

    def test_option_type_defaults_to_normal_and_accepts_uncertain_or_other(self):
        default_option = DiagnosisAskDecision.model_validate(self._ask()).questions[0].options[0]
        self.assertEqual(default_option.option_type, "normal")
        payload = self._ask()
        payload["questions"][0]["options"][0]["option_type"] = "uncertain"
        self.assertEqual(
            DiagnosisAskDecision.model_validate(payload).questions[0].options[0].option_type,
            "uncertain",
        )

    def test_ask_accepts_one_to_three_questions(self):
        for question_count in (1, 3):
            decision = DiagnosisAskDecision.model_validate(self._ask(question_count=question_count))
            self.assertEqual(len(decision.questions), question_count)

    def test_ask_rejects_zero_or_more_than_three_questions(self):
        with self.assertRaises(ValidationError):
            DiagnosisAskDecision.model_validate(self._ask(question_count=0))
        with self.assertRaises(ValidationError):
            DiagnosisAskDecision.model_validate(self._ask(question_count=4))

    def test_question_accepts_two_to_four_options(self):
        for option_count in (2, 4):
            decision = DiagnosisAskDecision.model_validate(self._ask(option_count=option_count))
            self.assertEqual(len(decision.questions[0].options), option_count)

    def test_question_rejects_option_counts_outside_range(self):
        for option_count in (1, 5):
            with self.subTest(option_count=option_count), self.assertRaises(ValidationError):
                DiagnosisAskDecision.model_validate(self._ask(option_count=option_count))

    def test_ask_rejects_duplicate_question_ids(self):
        payload = self._ask(question_count=2)
        payload["questions"][1]["question_id"] = "question-1"

        with self.assertRaises(ValidationError):
            DiagnosisAskDecision.model_validate(payload)

    def test_question_rejects_duplicate_option_ids(self):
        payload = self._ask()
        payload["questions"][0]["options"][1]["option_id"] = "option-1"

        with self.assertRaises(ValidationError):
            DiagnosisAskDecision.model_validate(payload)

    def test_rejects_invalid_action_blank_text_and_missing_required_fields(self):
        invalid_action = self._ask()
        invalid_action["action"] = "continue"
        blank_question = self._ask()
        blank_question["questions"][0]["text"] = "   "
        missing_questions = {"action": "ask"}

        adapter = TypeAdapter(DiagnosisDecision)
        for payload in (invalid_action, blank_question, missing_questions):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                adapter.validate_python(payload)

    def test_answer_requires_conclusion_recommendations_references_and_safety_notes(self):
        for missing_field, invalid_value in (
            ("conclusion", None),
            ("conclusion_evidence", []),
            ("recommendations", []),
            ("references", []),
            ("safety_notes", None),
        ):
            payload = self._answer()
            if invalid_value is None:
                del payload[missing_field]
            else:
                payload[missing_field] = invalid_value
            with self.subTest(missing_field=missing_field), self.assertRaises(ValidationError):
                DiagnosisAnswerDecision.model_validate(payload)

    def test_insufficient_requires_a_nonblank_reason_and_cannot_include_conclusion(self):
        missing_reason = self._insufficient()
        del missing_reason["reason"]
        disguised_answer = self._insufficient()
        disguised_answer["conclusion"] = "不能作为诊断结论"

        for payload in (missing_reason, disguised_answer):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                DiagnosisInsufficientDecision.model_validate(payload)

    def test_continue_request_accepts_a_batch_of_answers_and_optional_notes(self):
        request = DiagnosisContinueRequest.model_validate(
            {
                "diagnosis_id": "diagnosis-1",
                "request_id": "request-1",
                "expected_revision": 2,
                "answers": [
                    {"question_id": "question-1", "option_id": "option-1"},
                    {
                        "question_id": "question-2",
                        "option_id": "option-2",
                        "supplemental_note": "仅在首层打印时发生",
                    },
                ],
            }
        )

        self.assertEqual(len(request.answers), 2)
        self.assertIsNone(request.answers[0].supplemental_note)
        self.assertEqual(request.answers[1].supplemental_note, "仅在首层打印时发生")

    def test_continue_request_rejects_duplicate_questions_and_client_supplied_references(self):
        duplicate_answers = {
            "diagnosis_id": "diagnosis-1",
            "request_id": "request-1",
            "expected_revision": 0,
            "answers": [
                {"question_id": "question-1", "option_id": "option-1"},
                {"question_id": "question-1", "option_id": "option-2"},
            ],
        }
        forged_reference = {
            "diagnosis_id": "diagnosis-1",
            "request_id": "request-1",
            "expected_revision": 0,
            "answers": [
                {
                    "question_id": "question-1",
                    "option_id": "option-1",
                    "references": [self._reference("chunk:forged")],
                }
            ],
        }

        for payload in (duplicate_answers, forged_reference):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                DiagnosisContinueRequest.model_validate(payload)

    def test_start_and_response_reuse_the_supported_device_registry(self):
        start = DiagnosisStartRequest(device_id="creality-k1", original_problem="首层无法粘附")
        response = DiagnosisResponse.model_validate(
            {
                "diagnosis_id": "diagnosis-1",
                "device_id": "creality-k1",
                "decision": self._ask(),
                "clarification_round": 0,
                "status": "in_progress",
            }
        )

        self.assertEqual(start.device_id, "creality-k1")
        self.assertEqual(response.decision.action, "ask")
        with self.assertRaises(ValidationError):
            DiagnosisStartRequest(device_id="creality-k1-max", original_problem="异常")

    def test_query_request_keeps_qa_default_and_invalid_mode_still_returns_422(self):
        request = QueryRequest(query="如何调平？", session_id="session", is_stream=False)
        self.assertEqual(request.mode, "qa")

        client = TestClient(create_app())
        response = client.post(
            "/query",
            json={
                "query": "如何调平？",
                "session_id": "session",
                "is_stream": False,
                "mode": "unsupported",
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
