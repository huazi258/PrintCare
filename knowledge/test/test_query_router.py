import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from knowledge.api.query_router import create_app
from knowledge.core.deps import get_query_service
from knowledge.services.query_service import QueryService
from knowledge.utils import task_util


class FakeQueryService:
    def __init__(self):
        self.sessions = {
            "target-session": [{"role": "user", "text": "target"}],
            "other-session": [{"role": "user", "text": "other"}],
        }
        self.history_calls = []
        self.clear_calls = []

    def get_history(self, session_id, limit):
        self.history_calls.append((session_id, limit))
        return self.sessions.get(session_id, [])[:limit]

    def clear_history(self, session_id):
        self.clear_calls.append(session_id)
        return len(self.sessions.pop(session_id, []))


class QueryRouterTestCase(unittest.TestCase):
    def setUp(self):
        for store in (
            task_util._tasks_running_list,
            task_util._tasks_done_list,
            task_util._tasks_duration,
            task_util._tasks_result,
            task_util._tasks_status,
        ):
            store.clear()

        self.service = FakeQueryService()
        self.app = create_app()
        self.app.dependency_overrides[get_query_service] = lambda: self.service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_status_returns_pending_completed_and_failed_task_data(self):
        task_util.create_task("pending-task")
        pending = self.client.get("/status/pending-task")
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.json()["status"], task_util.TASK_STATUS_PENDING)

        task_util.update_task_status("processing-task", task_util.TASK_STATUS_PROCESSING)
        task_util.add_running_task("processing-task", "vector_search_node")
        processing = self.client.get("/status/processing-task")
        self.assertEqual(processing.status_code, 200)
        self.assertEqual(processing.json()["running_list"], ["切片搜索"])

        task_util.update_task_status("completed-task", task_util.TASK_STATUS_COMPLETED)
        task_util.add_done_task("completed-task", "answer_output_node")
        task_util.set_task_result("completed-task", "answer", "已生成答案")
        task_util.set_task_result("completed-task", "image_urls", ["https://example.test/image.png"])
        completed = self.client.get("/status/completed-task")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], task_util.TASK_STATUS_COMPLETED)
        self.assertEqual(completed.json()["done_list"], ["生成答案"])
        self.assertEqual(completed.json()["answer"], "已生成答案")
        self.assertEqual(completed.json()["image_urls"], ["https://example.test/image.png"])

        failed_service = QueryService()
        with patch("knowledge.services.query_service.query_app.invoke", side_effect=RuntimeError("模拟任务失败")):
            failed_service.run_query_graph("failed-session", "failed-task", "不调用模型", False)
        failed = self.client.get("/status/failed-task")
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(failed.json()["status"], task_util.TASK_STATUS_FAILED)
        self.assertEqual(failed.json()["error"], "模拟任务失败")

    def test_status_returns_404_for_unknown_task(self):
        response = self.client.get("/status/unknown-task")
        self.assertEqual(response.status_code, 404)
        self.assertIn("不存在或已失效", response.json()["detail"])

    def test_history_get_is_read_only_and_delete_only_clears_target_session(self):
        get_response = self.client.get("/history/target-session")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["items"], [{"role": "user", "text": "target"}])
        self.assertEqual(self.service.clear_calls, [])

        delete_response = self.client.delete("/history/target-session")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["deleted_count"], 1)
        self.assertEqual(self.service.clear_calls, ["target-session"])
        self.assertNotIn("target-session", self.service.sessions)
        self.assertIn("other-session", self.service.sessions)

    def test_openapi_exposes_correct_methods_and_existing_query_routes(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertEqual(set(paths["/history/{session_id}"].keys()), {"get", "delete"})
        self.assertIn("get", paths["/status/{task_id}"])
        self.assertIn("post", paths["/query"])
        self.assertIn("get", paths["/stream/{task_id}"])

    def test_generated_task_id_is_registered_as_pending(self):
        task_id = QueryService().generate_task_id()
        response = self.client.get(f"/status/{task_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], task_util.TASK_STATUS_PENDING)


if __name__ == "__main__":
    unittest.main()
