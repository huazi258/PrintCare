import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from knowledge.schema.diagnosis_schema import (
    DiagnosisAnswerDecision,
    DiagnosisAskDecision,
    DiagnosisContinueRequest,
    DiagnosisInsufficientDecision,
    DiagnosisStartRequest,
)
from knowledge.utils.diagnosis_session_util import (
    DiagnosisSessionConflictError,
    DiagnosisSessionNotFoundError,
    DiagnosisSessionRepository,
    DiagnosisSessionStateError,
    DiagnosisSessionStorageError,
)


class FakeCursor:
    def __init__(self, records):
        self.records = records

    def sort(self, key, direction):
        self.records.sort(key=lambda record: record[key], reverse=direction < 0)
        return self

    def limit(self, count):
        self.records = self.records[:count]
        return self

    def __iter__(self):
        return iter(self.records)


class FakeDiagnosisCollection:
    """Thread-safe in-memory stand-in for the MongoDB operations used here."""

    def __init__(self):
        self.documents = []
        self.indexes = []
        self.fail_next_update = False
        self._lock = threading.Lock()

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))
        return kwargs.get("name")

    def insert_one(self, document):
        with self._lock:
            if any(item["diagnosis_id"] == document["diagnosis_id"] for item in self.documents):
                from pymongo.errors import DuplicateKeyError

                raise DuplicateKeyError("duplicate diagnosis_id")
            stored = copy.deepcopy(document)
            stored["_id"] = len(self.documents) + 1
            self.documents.append(stored)
            return SimpleNamespace(inserted_id=stored["_id"])

    def find_one(self, query):
        with self._lock:
            for document in self.documents:
                if self._matches(document, query):
                    return copy.deepcopy(document)
        return None

    def find(self, query):
        with self._lock:
            return FakeCursor(
                [copy.deepcopy(document) for document in self.documents if self._matches(document, query)]
            )

    def find_one_and_update(self, query, update, return_document):
        with self._lock:
            if self.fail_next_update:
                self.fail_next_update = False
                raise RuntimeError("simulated database write failure")
            for document in self.documents:
                if self._matches(document, query):
                    self._apply_update(document, query, update)
                    return copy.deepcopy(document)
        return None

    def delete_one(self, query):
        with self._lock:
            for index, document in enumerate(self.documents):
                if self._matches(document, query):
                    self.documents.pop(index)
                    return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    @classmethod
    def _matches(cls, document, query):
        for key, expected in query.items():
            if key == "rounds" and "$elemMatch" in expected:
                if not any(cls._matches(round_record, expected["$elemMatch"]) for round_record in document["rounds"]):
                    return False
                continue
            values = cls._values(document, key.split("."))
            if isinstance(expected, dict) and "$ne" in expected:
                if any(value == expected["$ne"] for value in values):
                    return False
            elif not values or any(value != expected for value in values):
                return False
        return True

    @classmethod
    def _values(cls, value, path):
        if not path:
            return [value]
        if isinstance(value, list):
            return [nested for item in value for nested in cls._values(item, path)]
        if not isinstance(value, dict) or path[0] not in value:
            return []
        return cls._values(value[path[0]], path[1:])

    @classmethod
    def _apply_update(cls, document, query, update):
        round_index = None
        round_condition = query.get("rounds", {}).get("$elemMatch")
        if round_condition:
            round_index = next(
                index
                for index, round_record in enumerate(document["rounds"])
                if cls._matches(round_record, round_condition)
            )

        for key, value in update.get("$set", {}).items():
            if key.startswith("rounds.$."):
                document["rounds"][round_index][key.removeprefix("rounds.$.")] = copy.deepcopy(value)
            else:
                document[key] = copy.deepcopy(value)
        for key, value in update.get("$inc", {}).items():
            document[key] += value
        for key, value in update.get("$push", {}).items():
            if isinstance(value, dict) and "$each" in value:
                document[key].extend(copy.deepcopy(value["$each"]))
            else:
                document[key].append(copy.deepcopy(value))


class DiagnosisSessionRepositoryTestCase(unittest.TestCase):
    def setUp(self):
        self.collection = FakeDiagnosisCollection()
        self.repository = DiagnosisSessionRepository(collection=self.collection)

    @staticmethod
    def _start_request():
        return DiagnosisStartRequest(device_id="creality-k1", original_problem="首层无法粘附")

    @staticmethod
    def _ask_decision(question_id="question-1"):
        return DiagnosisAskDecision.model_validate(
            {
                "action": "ask",
                "questions": [
                    {
                        "question_id": question_id,
                        "text": "异常在什么时候发生？",
                        "options": [
                            {"option_id": "option-1", "text": "首层打印时"},
                            {"option_id": "option-2", "text": "其他阶段"},
                        ],
                        "references": [{"source_id": "chunk:101"}],
                    }
                ],
            }
        )

    @staticmethod
    def _answer_decision():
        return DiagnosisAnswerDecision.model_validate(
            {
                "action": "answer",
                "conclusion": "资料指向首层调平设置需要检查。",
                "recommendations": ["按 K1 手册检查调平设置。"],
                "references": [{"source_id": "chunk:101"}],
                "safety_notes": [],
            }
        )

    @staticmethod
    def _insufficient_decision():
        return DiagnosisInsufficientDecision.model_validate(
            {
                "action": "insufficient",
                "reason": "现有本地资料未覆盖该现象。",
                "confirmed_facts": [],
                "next_steps": ["补充信息或联系官方支持。"],
            }
        )

    @staticmethod
    def _answer_request(diagnosis_id, request_id, revision, option_id="option-1"):
        return DiagnosisContinueRequest.model_validate(
            {
                "diagnosis_id": diagnosis_id,
                "request_id": request_id,
                "expected_revision": revision,
                "answers": [
                    {
                        "question_id": "question-1",
                        "option_id": option_id,
                        "supplemental_note": "只在首层发生",
                    }
                ],
            }
        )

    def _create(self, diagnosis_id="diagnosis-1", visitor_id="visitor-a"):
        return self.repository.create_session(
            visitor_id, self._start_request(), diagnosis_id=diagnosis_id
        )

    def test_create_read_list_and_delete_are_visitor_scoped(self):
        created = self._create()
        self.repository.create_session("visitor-a", self._start_request(), diagnosis_id="diagnosis-2")

        self.assertEqual(created["device_model"], "Creality K1")
        self.assertEqual(created["status"], "in_progress")
        self.assertEqual(self.repository.get_session("diagnosis-1", "visitor-b"), None)
        self.assertEqual(
            {session["diagnosis_id"] for session in self.repository.list_sessions("visitor-a")},
            {"diagnosis-1", "diagnosis-2"},
        )
        self.assertFalse(self.repository.delete_session("diagnosis-1", "visitor-b"))
        self.assertTrue(self.repository.delete_session("diagnosis-1", "visitor-a"))
        self.assertIsNone(self.repository.get_session("diagnosis-1", "visitor-a"))
        self.assertTrue(any(config.get("unique") for _, config in self.collection.indexes))

    def test_rounds_answers_references_and_facts_are_persisted_for_recovery(self):
        created = self._create()
        after_questions = self.repository.save_question_round(
            created["diagnosis_id"], "visitor-a", self._ask_decision(), expected_revision=0
        )
        after_answers = self.repository.save_answers(
            "visitor-a", self._answer_request(created["diagnosis_id"], "request-1", revision=1)
        ).session

        restored = self.repository.get_session(created["diagnosis_id"], "visitor-a")
        self.assertEqual(after_questions["clarification_count"], 1)
        self.assertEqual(after_answers["revision"], 2)
        self.assertEqual(restored["rounds"][0]["questions"][0]["references"][0]["source_id"], "chunk:101")
        self.assertEqual(restored["rounds"][0]["answers"][0]["option_id"], "option-1")
        self.assertEqual(restored["facts"][0]["question_id"], "question-1")

    def test_duplicate_request_id_stays_idempotent_even_after_a_later_round(self):
        created = self._create()
        self.repository.save_question_round(created["diagnosis_id"], "visitor-a", self._ask_decision(), 0)
        first_request = self._answer_request(created["diagnosis_id"], "request-1", revision=1)
        first = self.repository.save_answers("visitor-a", first_request)
        self.repository.save_question_round(
            created["diagnosis_id"], "visitor-a", self._ask_decision("question-2"), 2
        )

        duplicate = self.repository.save_answers("visitor-a", first_request)
        restored = self.repository.get_session(created["diagnosis_id"], "visitor-a")
        self.assertFalse(first.idempotent)
        self.assertTrue(duplicate.idempotent)
        self.assertEqual(duplicate.request_record["revision_after"], 2)
        self.assertEqual(restored["revision"], 3)
        self.assertEqual(len(restored["rounds"][0]["answers"]), 1)

    def test_batch_answers_for_multiple_current_questions_are_saved_atomically(self):
        created = self._create()
        decision_payload = self._ask_decision().model_dump(mode="json")
        second_question = copy.deepcopy(decision_payload["questions"][0])
        second_question["question_id"] = "question-2"
        decision_payload["questions"].append(second_question)
        self.repository.save_question_round(
            created["diagnosis_id"],
            "visitor-a",
            DiagnosisAskDecision.model_validate(decision_payload),
            0,
        )
        request = DiagnosisContinueRequest.model_validate(
            {
                "diagnosis_id": created["diagnosis_id"],
                "request_id": "request-1",
                "expected_revision": 1,
                "answers": [
                    {"question_id": "question-1", "option_id": "option-1"},
                    {"question_id": "question-2", "option_id": "option-2"},
                ],
            }
        )

        saved = self.repository.save_answers("visitor-a", request).session
        self.assertEqual(len(saved["rounds"][0]["answers"]), 2)
        self.assertEqual(len(saved["facts"]), 2)

    def test_stale_revision_and_other_visitor_writes_are_rejected(self):
        created = self._create()
        self.repository.save_question_round(created["diagnosis_id"], "visitor-a", self._ask_decision(), 0)
        self.repository.save_answers(
            "visitor-a", self._answer_request(created["diagnosis_id"], "request-1", revision=1)
        )

        with self.assertRaises(DiagnosisSessionConflictError):
            self.repository.save_answers(
                "visitor-a", self._answer_request(created["diagnosis_id"], "request-2", revision=1)
            )
        with self.assertRaises(DiagnosisSessionNotFoundError):
            self.repository.save_question_round(
                created["diagnosis_id"], "visitor-b", self._ask_decision(), 2
            )

    def test_answers_must_match_every_question_and_option_in_the_current_round(self):
        created = self._create()
        self.repository.save_question_round(created["diagnosis_id"], "visitor-a", self._ask_decision(), 0)

        with self.assertRaises(DiagnosisSessionStateError):
            self.repository.save_answers(
                "visitor-a",
                self._answer_request(
                    created["diagnosis_id"], "request-1", revision=1, option_id="unknown-option"
                ),
            )

    def test_concurrent_different_requests_allow_only_one_revision_guarded_update(self):
        created = self._create()
        self.repository.save_question_round(created["diagnosis_id"], "visitor-a", self._ask_decision(), 0)

        def submit(request_id):
            try:
                return self.repository.save_answers(
                    "visitor-a", self._answer_request(created["diagnosis_id"], request_id, revision=1)
                )
            except DiagnosisSessionConflictError:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(submit, ["request-1", "request-2"]))

        restored = self.repository.get_session(created["diagnosis_id"], "visitor-a")
        self.assertEqual(sum(result == "conflict" for result in results), 1)
        self.assertEqual(restored["revision"], 2)
        self.assertEqual(len(restored["rounds"][0]["answers"]), 1)
        self.assertEqual(len(restored["facts"]), 1)

    def test_state_transitions_do_not_auto_resolve_and_reject_terminal_changes(self):
        created = self._create()
        after_result = self.repository.save_final_result(
            created["diagnosis_id"], "visitor-a", self._answer_decision(), expected_revision=0
        )
        after_feedback = self.repository.set_feedback(
            created["diagnosis_id"], "visitor-a", "resolved", expected_revision=1
        )

        self.assertEqual(after_result["status"], "pending_verification")
        self.assertEqual(after_feedback["status"], "resolved")
        self.assertEqual(after_feedback["feedback"]["status"], "resolved")
        with self.assertRaises(DiagnosisSessionStateError):
            self.repository.transition_status(
                created["diagnosis_id"], "visitor-a", "ended", expected_revision=2
            )

        insufficient = self._create("diagnosis-2")
        terminal = self.repository.save_final_result(
            insufficient["diagnosis_id"], "visitor-a", self._insufficient_decision(), 0
        )
        self.assertEqual(terminal["status"], "insufficient")
        with self.assertRaises(DiagnosisSessionStateError):
            self.repository.set_feedback(insufficient["diagnosis_id"], "visitor-a", "resolved", 1)

    def test_failed_database_write_does_not_return_success_or_advance_session(self):
        created = self._create()
        self.repository.save_question_round(created["diagnosis_id"], "visitor-a", self._ask_decision(), 0)
        before = self.repository.get_session(created["diagnosis_id"], "visitor-a")
        self.collection.fail_next_update = True

        with self.assertRaises(DiagnosisSessionStorageError):
            self.repository.save_answers(
                "visitor-a", self._answer_request(created["diagnosis_id"], "request-1", revision=1)
            )

        self.assertEqual(self.repository.get_session(created["diagnosis_id"], "visitor-a"), before)


if __name__ == "__main__":
    unittest.main()
