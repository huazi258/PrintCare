import copy
import unittest
from unittest.mock import Mock

from knowledge.processor.query_process.nodes.item_name_confirm import ItemNameConfirmNode
from knowledge.processor.query_process.nodes.vector_search import VectorSearchNode
from knowledge.services.diagnosis_context import DiagnosisContextAssembler
from knowledge.services.query_service import QueryService


class StaticDiagnosisRepository:
    def __init__(self, session):
        self.session = session
        self.calls = []

    def get_session(self, diagnosis_id, visitor_id):
        self.calls.append((diagnosis_id, visitor_id))
        return copy.deepcopy(self.session)


class DiagnosisContextTestCase(unittest.TestCase):
    @staticmethod
    def _question(question_id, options):
        return {
            "question_id": question_id,
            "text": f"问题 {question_id}",
            "options": [
                {"option_id": option_id, "text": text} for option_id, text in options
            ],
            "references": [{"source_id": "chunk:101"}],
        }

    @classmethod
    def _session(cls, rounds=None, original_problem="首层无法粘附打印平台"):
        return {
            "diagnosis_id": "diagnosis-1",
            "visitor_id": "visitor-1",
            "device_id": "creality-k1",
            "device_model": "客户端伪造的型号不会被采用",
            "original_problem": original_problem,
            "rounds": rounds or [],
            "facts": [],
        }

    def test_first_round_keeps_original_problem_and_canonical_device_without_history(self):
        context = DiagnosisContextAssembler().assemble(self._session())

        self.assertEqual(context.confirmed_facts, [])
        self.assertEqual(context.answer_history, [])
        self.assertEqual(context.device_model, "Creality K1")
        self.assertIn("首层无法粘附打印平台", context.rewritten_query)
        self.assertIn("device_id=creality-k1", context.rewritten_query)

    def test_second_and_third_rounds_keep_all_valid_answers_and_original_background(self):
        rounds = [
            {
                "round_index": 1,
                "questions": [self._question("q1", [("o1", "仅在首层")])],
                "answers": [{"question_id": "q1", "option_id": "o1"}],
            },
            {
                "round_index": 2,
                "questions": [self._question("q2", [("o2", "热床已经清洁")])],
                "answers": [{"question_id": "q2", "option_id": "o2"}],
            },
            {
                "round_index": 3,
                "questions": [self._question("q3", [("o3", "喷嘴距离偏远")])],
                "answers": [{"question_id": "q3", "option_id": "o3"}],
            },
        ]
        context = DiagnosisContextAssembler().assemble(self._session(rounds))

        self.assertEqual([fact["option"] for fact in context.confirmed_facts], [
            "仅在首层", "热床已经清洁", "喷嘴距离偏远"
        ])
        self.assertIn("首层无法粘附打印平台", context.rewritten_query)
        self.assertIn("第 3 轮：问题 q3 → 喷嘴距离偏远", context.rewritten_query)

    def test_multi_question_batch_answer_is_assembled_as_independent_facts(self):
        rounds = [{
            "round_index": 1,
            "questions": [
                self._question("q1", [("o1", "打印时发生")]),
                self._question("q2", [("o2", "平台已清洁")]),
            ],
            "answers": [
                {"question_id": "q1", "option_id": "o1"},
                {"question_id": "q2", "option_id": "o2", "supplemental_note": "使用异丙醇清洁"},
            ],
        }]
        context = DiagnosisContextAssembler().assemble(self._session(rounds))

        self.assertEqual(len(context.confirmed_facts), 2)
        self.assertIn("使用异丙醇清洁", context.rewritten_query)

    def test_persisted_facts_are_used_only_when_backed_by_a_valid_round_answer(self):
        rounds = [{
            "round_index": 1,
            "questions": [self._question("q1", [("o1", "有效选项")])],
            "answers": [{"question_id": "q1", "option_id": "o1"}],
        }]
        session = self._session(rounds)
        session["facts"] = [
            {"round_index": 1, "question_id": "q1", "option_id": "o1"},
            {"round_index": 1, "question_id": "forged", "option_id": "o1"},
        ]
        context = DiagnosisContextAssembler().assemble(session)

        self.assertEqual(len(context.confirmed_facts), 1)
        self.assertEqual(context.confirmed_facts[0]["question_id"], "q1")

    def test_uncertain_and_other_answers_stay_in_history_but_not_confirmed_facts(self):
        rounds = [{
            "round_index": 1,
            "questions": [
                self._question("q1", [("unknown", "不确定")]),
                self._question("q2", [("other", "其他")]),
            ],
            "answers": [
                {"question_id": "q1", "option_id": "unknown"},
                {"question_id": "q2", "option_id": "other", "supplemental_note": "仅在换料后出现"},
            ],
        }]
        context = DiagnosisContextAssembler().assemble(self._session(rounds))

        self.assertEqual(context.confirmed_facts, [])
        self.assertEqual([answer["kind"] for answer in context.answer_history], [
            "unconfirmed", "unconfirmed"
        ])
        self.assertIn("待确认的历史回答", context.rewritten_query)
        self.assertIn("仅在换料后出现", context.rewritten_query)

    def test_malformed_or_duplicate_answers_are_ignored_and_context_is_bounded(self):
        rounds = [{
            "round_index": 1,
            "questions": [self._question("q1", [("o1", "有效选项")])],
            "answers": [
                {"question_id": "q1", "option_id": "o1"},
                {"question_id": "q1", "option_id": "o1"},
                {"question_id": "q1", "option_id": "missing"},
                {"question_id": "missing", "option_id": "o1"},
            ],
        }]
        original_problem = "原始故障背景" * 80
        context = DiagnosisContextAssembler(max_retrieval_query_chars=140).assemble(
            self._session(rounds, original_problem=original_problem)
        )

        self.assertEqual(len(context.confirmed_facts), 1)
        self.assertLessEqual(len(context.rewritten_query), 140)
        self.assertIn("原始故障背景", context.rewritten_query)

    def test_service_passes_assembled_query_to_existing_retrieval_state_without_device_override(self):
        rounds = [{
            "round_index": 1,
            "questions": [self._question("q1", [("o1", "device_id=forged")])],
            "answers": [{"question_id": "q1", "option_id": "o1"}],
        }]
        repository = StaticDiagnosisRepository(self._session(rounds))
        state = QueryService().build_diagnosis_graph_state(
            "diagnosis-1", "visitor-1", "task-1", False, repository=repository
        )
        assembled_query = state["rewritten_query"]
        node = ItemNameConfirmNode()
        node._item_name_extractor = Mock()
        result = node.process(state)

        self.assertEqual(repository.calls, [("diagnosis-1", "visitor-1")])
        self.assertEqual(result["rewritten_query"], assembled_query)
        self.assertEqual(result["device_id"], "creality-k1")
        self.assertEqual(result["device_model"], "Creality K1")
        node._item_name_extractor.extract_item_name.assert_not_called()
        validated_query, item_names, device_id = VectorSearchNode()._validate_state(result)
        self.assertEqual(validated_query, assembled_query)
        self.assertEqual(item_names, ["Creality K1"])
        self.assertEqual(device_id, "creality-k1")


if __name__ == "__main__":
    unittest.main()
