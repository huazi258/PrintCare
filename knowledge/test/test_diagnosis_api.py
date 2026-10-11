import unittest

from fastapi.testclient import TestClient

from knowledge.api.query_router import create_app
from knowledge.core.deps import get_diagnosis_service, get_query_service
from knowledge.services.diagnosis_service import DiagnosisService
from knowledge.test.test_diagnosis_session_repository import FakeDiagnosisCollection
from knowledge.utils.diagnosis_session_util import DiagnosisSessionRepository
from knowledge.utils import task_util


ASK_DECISION = {
    "action": "ask",
    "questions": [{
        "question_id": "first-layer",
        "text": "异常是否只发生在首层？",
        "options": [
            {"option_id": "yes", "text": "是", "option_type": "normal"},
            {"option_id": "no", "text": "否", "option_type": "normal"},
        ],
        "references": [{
            "source_id": "chunk:101",
            "excerpt": "首层粘附异常时，请检查首层调平设置。",
            "support_text": "首层粘附异常",
        }],
    }],
}

ANSWER_DECISION = {
    "action": "answer",
    "conclusion": "资料指向首层调平设置需要检查。",
    "conclusion_evidence": [{
        "source_id": "chunk:101",
        "excerpt": "首层粘附异常时，请检查首层调平设置。",
        "support_text": "首层调平设置",
    }],
    "recommendations": [{
        "text": "请检查首层调平设置。",
        "evidence": [{
            "source_id": "chunk:101",
            "excerpt": "首层粘附异常时，请检查首层调平设置。",
            "support_text": "检查首层调平设置",
        }],
    }],
    "references": [{"source_id": "chunk:101"}],
    "safety_notes": [],
}

INSUFFICIENT_DECISION = {
    "action": "insufficient",
    "reason": "候选建议未通过证据校验。",
    "confirmed_facts": [],
    "next_steps": ["停止操作并联系官方支持。"],
}


class StubQueryService:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.graph_calls = 0
        self.task_count = 0

    def generate_task_id(self, visitor_id=None, mode="qa"):
        self.task_count += 1
        task_id = f"diagnosis-task-{self.task_count}"
        task_util.create_task(task_id, visitor_id=visitor_id, mode=mode)
        return task_id

    def build_diagnosis_graph_state(self, diagnosis_id, visitor_id, task_id, is_stream, repository):
        return {"diagnosis_id": diagnosis_id, "task_id": task_id, "mode": "diagnosis"}

    def run_diagnosis_graph(self, _state):
        self.graph_calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def graph_result(decision, *, status="validated", passed=True):
    return {
        "diagnosis_status": status,
        "diagnosis_validation_passed": passed,
        "diagnosis_validated": decision,
        "diagnosis_validation_error": {"code": "invalid_reference"}
        if status == "validation_rejected" else {},
    }


class DiagnosisApiTestCase(unittest.TestCase):
    def setUp(self):
        for store in (
            task_util._tasks_running_list,
            task_util._tasks_done_list,
            task_util._tasks_duration,
            task_util._tasks_result,
            task_util._tasks_status,
            task_util._tasks_owner,
        ):
            store.clear()
        self.collection = FakeDiagnosisCollection()
        self.repository = DiagnosisSessionRepository(collection=self.collection)
        self.query_service = StubQueryService([
            graph_result(ASK_DECISION), graph_result(ANSWER_DECISION)
        ])
        self.diagnosis_service = DiagnosisService(
            query_service=self.query_service, repository=self.repository
        )
        self.app = create_app()
        self.app.dependency_overrides[get_query_service] = lambda: self.query_service
        self.app.dependency_overrides[get_diagnosis_service] = lambda: self.diagnosis_service
        self.client = TestClient(self.app)
        self.headers = {"X-Visitor-ID": "visitor-a"}

    def tearDown(self):
        self.app.dependency_overrides.clear()

    @staticmethod
    def _start_payload(**overrides):
        payload = {
            "mode": "diagnosis",
            "device_id": "creality-k1",
            "original_problem": "首层无法粘附打印平台",
            "request_id": "start-1",
            "is_stream": False,
        }
        payload.update(overrides)
        return payload

    def _start(self):
        response = self.client.post("/query", json=self._start_payload(), headers=self.headers)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_start_continue_answer_feedback_recovery_and_delete(self):
        started = self._start()
        diagnosis_id = started["diagnosis_id"]
        self.assertEqual(started["decision"]["action"], "ask")
        self.assertEqual(started["clarification_round"], 1)
        self.assertEqual(started["status"], "in_progress")
        task_status = self.client.get(f"/status/{started['task_id']}", headers=self.headers)
        self.assertEqual(task_status.status_code, 200)
        self.assertEqual(task_status.json()["diagnosis"]["decision"]["action"], "ask")

        detail = self.client.get(f"/diagnoses/{diagnosis_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["rounds"][0]["questions"][0]["question_id"], "first-layer")

        continued = self.client.post(
            "/query",
            json={
                "mode": "diagnosis",
                "diagnosis_id": diagnosis_id,
                "request_id": "continue-1",
                "expected_revision": started["revision"],
                "answers": [{"question_id": "first-layer", "option_id": "yes"}],
            },
            headers=self.headers,
        )
        self.assertEqual(continued.status_code, 200)
        self.assertEqual(continued.json()["decision"]["action"], "answer")
        self.assertEqual(continued.json()["status"], "pending_verification")

        feedback = self.client.post(
            f"/diagnoses/{diagnosis_id}/feedback",
            json={"status": "resolved", "expected_revision": continued.json()["revision"]},
            headers=self.headers,
        )
        self.assertEqual(feedback.status_code, 200)
        self.assertEqual(feedback.json()["status"], "resolved")

        listed = self.client.get("/diagnoses", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["items"][0]["diagnosis_id"], diagnosis_id)
        deleted = self.client.delete(f"/diagnoses/{diagnosis_id}", headers=self.headers)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get(f"/diagnoses/{diagnosis_id}", headers=self.headers).status_code, 404)

    def test_duplicate_start_and_continue_do_not_rerun_graph(self):
        started = self._start()
        duplicate_start = self.client.post("/query", json=self._start_payload(), headers=self.headers)
        self.assertEqual(duplicate_start.status_code, 200)
        self.assertTrue(duplicate_start.json()["idempotent"])
        self.assertEqual(duplicate_start.json()["diagnosis_id"], started["diagnosis_id"])
        self.assertEqual(self.query_service.graph_calls, 1)

        continue_payload = {
            "mode": "diagnosis",
            "diagnosis_id": started["diagnosis_id"],
            "request_id": "continue-1",
            "expected_revision": started["revision"],
            "answers": [{"question_id": "first-layer", "option_id": "yes"}],
        }
        first = self.client.post("/query", json=continue_payload, headers=self.headers)
        duplicate = self.client.post("/query", json=continue_payload, headers=self.headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["idempotent"])
        self.assertEqual(self.query_service.graph_calls, 2)

    def test_validation_rejection_only_persists_safe_insufficient_result(self):
        self.query_service.outcomes = [
            graph_result(INSUFFICIENT_DECISION, status="validation_rejected", passed=False)
        ]
        response = self.client.post(
            "/query", json=self._start_payload(request_id="rejected-start"), headers=self.headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "insufficient")
        self.assertEqual(response.json()["decision"]["action"], "insufficient")
        stored = self.repository.get_session(response.json()["diagnosis_id"], "visitor-a")
        self.assertEqual(stored["result"]["action"], "insufficient")
        self.assertEqual(stored["result_metadata"]["rejection"]["code"], "invalid_reference")

    def test_unresolved_feedback_can_resume_only_within_the_round_limit(self):
        started = self._start()
        continued = self.client.post(
            "/query",
            json={
                "mode": "diagnosis",
                "diagnosis_id": started["diagnosis_id"],
                "request_id": "continue-1",
                "expected_revision": started["revision"],
                "answers": [{"question_id": "first-layer", "option_id": "no"}],
            },
            headers=self.headers,
        )
        feedback = self.client.post(
            f"/diagnoses/{started['diagnosis_id']}/feedback",
            json={"status": "unresolved", "expected_revision": continued.json()["revision"]},
            headers=self.headers,
        )
        self.assertEqual(feedback.json()["status"], "unresolved")

        self.query_service.outcomes.append(graph_result(ASK_DECISION))
        resumed = self.client.post(
            "/query",
            json={
                "mode": "diagnosis",
                "diagnosis_id": started["diagnosis_id"],
                "request_id": "resume-1",
                "expected_revision": feedback.json()["revision"],
                "resume_unresolved": True,
            },
            headers=self.headers,
        )
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["status"], "in_progress")
        self.assertEqual(resumed.json()["clarification_round"], 2)
        self.assertEqual(resumed.json()["decision"]["action"], "ask")

    def test_end_rejects_later_answer_submission(self):
        started = self._start()
        ended = self.client.post(
            f"/diagnoses/{started['diagnosis_id']}/end",
            json={"expected_revision": started["revision"]},
            headers=self.headers,
        )
        self.assertEqual(ended.status_code, 200)
        self.assertEqual(ended.json()["status"], "ended")
        rejected = self.client.post(
            "/query",
            json={
                "mode": "diagnosis",
                "diagnosis_id": started["diagnosis_id"],
                "request_id": "after-end",
                "expected_revision": ended.json()["revision"],
                "answers": [{"question_id": "first-layer", "option_id": "yes"}],
            },
            headers=self.headers,
        )
        self.assertEqual(rejected.status_code, 409)

    def test_model_failure_releases_lease_for_safe_retry(self):
        self.query_service.outcomes = [RuntimeError("model timeout"), graph_result(ASK_DECISION)]
        failed = self.client.post(
            "/query", json=self._start_payload(request_id="retry-start"), headers=self.headers
        )
        self.assertEqual(failed.status_code, 503)
        session = self.repository.list_sessions("visitor-a")[0]
        self.assertIsNone(session["execution"])
        self.assertEqual(session["status"], "in_progress")

        retried = self.client.post(
            "/query", json=self._start_payload(request_id="retry-start"), headers=self.headers
        )
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json()["decision"]["action"], "ask")
        self.assertEqual(self.query_service.graph_calls, 2)

    def test_visitors_cannot_read_other_sessions_or_diagnosis_tasks(self):
        started = self._start()
        other_headers = {"X-Visitor-ID": "visitor-b"}

        self.assertEqual(
            self.client.get(f"/diagnoses/{started['diagnosis_id']}", headers=other_headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/status/{started['task_id']}", headers=other_headers).status_code,
            404,
        )

    def test_stream_emits_only_persisted_diagnosis_then_final_and_closes(self):
        response = self.client.post(
            "/query",
            json=self._start_payload(is_stream=True, request_id="stream-start"),
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        with self.client.stream(
            "GET", f"/stream/{response.json()['task_id']}", headers=self.headers
        ) as stream:
            payload = b"".join(stream.iter_bytes()).decode("utf-8")

        self.assertIn("event: progress", payload)
        self.assertIn("event: diagnosis", payload)
        self.assertIn("event: final", payload)
        self.assertLess(payload.index("event: diagnosis"), payload.index("event: final"))


if __name__ == "__main__":
    unittest.main()
