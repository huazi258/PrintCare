import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from knowledge.api.query_router import create_app
from knowledge.core.deps import get_query_service
from knowledge.processor.query_process import main_graph
from knowledge.processor.query_process.nodes.diagnosis_placeholder import DiagnosisPlaceholderNode
from knowledge.processor.query_process.nodes.rerank import RerankNode
from knowledge.processor.query_process.nodes.web_search_mcp import WebSearchMcpNode
from knowledge.services.query_service import QueryService


class RecordingQueryService:
    def __init__(self):
        self.created_task_ids = []
        self.run_calls = []

    def generate_session_id(self):
        return "generated-session"

    def generate_task_id(self):
        task_id = f"task-{len(self.created_task_ids) + 1}"
        self.created_task_ids.append(task_id)
        return task_id

    def run_query_graph(self, *args):
        self.run_calls.append(args)

    def get_answer(self, _task_id):
        return "mock answer"


class RecordingNode:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {}

    def __call__(self, state):
        self.calls.append(dict(state))
        return dict(self.result)


class QueryModeRoutingTestCase(unittest.TestCase):
    def setUp(self):
        self.service = RecordingQueryService()
        self.app = create_app()
        self.app.dependency_overrides[get_query_service] = lambda: self.service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    @staticmethod
    def _payload(**overrides):
        payload = {"query": "K1 如何调平？", "session_id": "session", "is_stream": False}
        payload.update(overrides)
        return payload

    def test_mode_defaults_to_qa_and_explicit_qa_keeps_query_contract(self):
        default_response = self.client.post("/query", json=self._payload())
        explicit_response = self.client.post("/query", json=self._payload(mode="qa"))

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(explicit_response.status_code, 200)
        self.assertEqual([call[-1] for call in self.service.run_calls], ["qa", "qa"])

    def test_invalid_mode_is_rejected_by_request_contract(self):
        response = self.client.post("/query", json=self._payload(mode="unsupported"))

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.created_task_ids, [])
        self.assertEqual(self.service.run_calls, [])

    def test_diagnosis_api_fails_closed_before_task_or_sse_queue(self):
        with patch("knowledge.api.query_router.create_sse_queue") as create_sse_queue:
            response = self.client.post("/query", json=self._payload(mode="diagnosis", is_stream=True))

        self.assertEqual(response.status_code, 501)
        self.assertIn("尚未开放", response.json()["detail"])
        self.assertEqual(self.service.created_task_ids, [])
        self.assertEqual(self.service.run_calls, [])
        create_sse_queue.assert_not_called()

    def test_service_passes_mode_to_graph_and_rejects_invalid_direct_call(self):
        service = QueryService()
        with patch("knowledge.services.query_service.query_app.invoke") as invoke:
            service.run_query_graph("session", "task", "question", False, mode="diagnosis")

        self.assertEqual(invoke.call_args.args[0]["mode"], "diagnosis")
        with self.assertRaises(ValueError):
            service.run_query_graph("session", "task", "question", False, mode="unsupported")

    def test_mode_routing_selects_qa_or_diagnosis_after_rerank(self):
        self.assertEqual(main_graph.route_after_rerank({"mode": "qa"}), "answer_output")
        self.assertEqual(main_graph.route_after_rerank({"mode": "diagnosis"}), "diagnosis_placeholder")

    def test_early_answer_never_sends_diagnosis_to_normal_answer_output(self):
        self.assertEqual(
            main_graph.route_after_item_confirm({"mode": "qa", "answer": "existing answer"}),
            "answer_output",
        )
        self.assertEqual(
            main_graph.route_after_item_confirm({"mode": "diagnosis", "answer": "existing answer"}),
            "diagnosis_placeholder",
        )

    def test_placeholder_has_no_answer_or_history_side_effects(self):
        state = DiagnosisPlaceholderNode().process({"answer": "do not persist me"})

        self.assertEqual(state["answer"], "")
        self.assertEqual(state["diagnosis_status"], "not_available")
        self.assertIn("尚未开放", state["diagnosis_message"])

    @staticmethod
    def _create_recording_graph(item_result=None):
        nodes = {
            "item": RecordingNode(item_result),
            "vector": RecordingNode({"embedding_chunks": []}),
            "hyde": RecordingNode({"hyde_embedding_chunks": []}),
            "web": RecordingNode({"web_search_docs": []}),
            "rrf": RecordingNode({"rrf_chunks": []}),
            "rerank": RecordingNode({"reranked_docs": []}),
            "answer": RecordingNode({"answer": "qa answer"}),
            "diagnosis": RecordingNode(
                {
                    "answer": "",
                    "diagnosis_status": "not_available",
                    "diagnosis_message": "诊断功能尚未开放",
                }
            ),
        }
        with patch.object(main_graph, "ItemNameConfirmNode", return_value=nodes["item"]), patch.object(
            main_graph, "VectorSearchNode", return_value=nodes["vector"]
        ), patch.object(main_graph, "HyDeSearchNode", return_value=nodes["hyde"]), patch.object(
            main_graph, "WebSearchMcpNode", return_value=nodes["web"]
        ), patch.object(main_graph, "RrfNode", return_value=nodes["rrf"]), patch.object(
            main_graph, "RerankNode", return_value=nodes["rerank"]
        ), patch.object(main_graph, "AnswerOutputNode", return_value=nodes["answer"]), patch.object(
            main_graph, "DiagnosisPlaceholderNode", return_value=nodes["diagnosis"]
        ):
            graph = main_graph.create_query_graph()
        return graph, nodes

    def test_compiled_qa_graph_executes_three_searches_then_shared_rrf_rerank(self):
        graph, nodes = self._create_recording_graph()
        result = graph.invoke({"mode": "qa", "original_query": "打印失败"})

        for node_name in ("vector", "hyde", "web", "rrf", "rerank", "answer"):
            self.assertEqual(len(nodes[node_name].calls), 1, node_name)
        self.assertEqual(nodes["diagnosis"].calls, [])
        self.assertEqual(result["answer"], "qa answer")

    def test_compiled_diagnosis_graph_executes_local_searches_only_then_placeholder(self):
        graph, nodes = self._create_recording_graph()
        result = graph.invoke({"mode": "diagnosis", "original_query": "打印失败"})

        for node_name in ("vector", "hyde", "rrf", "rerank", "diagnosis"):
            self.assertEqual(len(nodes[node_name].calls), 1, node_name)
        self.assertEqual(nodes["web"].calls, [])
        self.assertEqual(nodes["answer"].calls, [])
        self.assertEqual(result["diagnosis_status"], "not_available")
        self.assertEqual(result["answer"], "")

    def test_compiled_diagnosis_early_answer_skips_all_searches_and_normal_output(self):
        graph, nodes = self._create_recording_graph(item_result={"answer": "existing answer"})
        result = graph.invoke({"mode": "diagnosis", "original_query": "打印失败"})

        for node_name in ("vector", "hyde", "web", "rrf", "rerank", "answer"):
            self.assertEqual(nodes[node_name].calls, [], node_name)
        self.assertEqual(len(nodes["diagnosis"].calls), 1)
        self.assertEqual(result["diagnosis_status"], "not_available")

    def test_web_mcp_node_blocks_diagnosis_and_unknown_modes_before_client_creation(self):
        node = WebSearchMcpNode()
        input_state = {"rewritten_query": "打印失败", "item_names": ["Creality K1"]}

        with patch(
            "knowledge.processor.query_process.nodes.web_search_mcp.MCPServerStreamableHttp"
        ) as client_factory, patch.object(
            node, "_create_execute_web_search", new_callable=AsyncMock
        ) as execute_web_search:
            diagnosis_state = {**input_state, "mode": "diagnosis"}
            invalid_mode_state = {**input_state, "mode": "unsupported"}
            self.assertIs(node.process(diagnosis_state), diagnosis_state)
            self.assertIs(node.process(invalid_mode_state), invalid_mode_state)

        client_factory.assert_not_called()
        execute_web_search.assert_not_awaited()

    def test_web_mcp_node_keeps_legacy_qa_default(self):
        node = WebSearchMcpNode()
        input_state = {"rewritten_query": "打印失败", "item_names": ["Creality K1"]}
        with patch.object(node, "_create_execute_web_search", new_callable=AsyncMock, return_value=[]) as execute:
            result = node.process(input_state)

        execute.assert_awaited_once_with("打印失败")
        self.assertIs(result, input_state)

    def test_rerank_excludes_injected_web_docs_for_diagnosis_only(self):
        state = {
            "rrf_chunks": [{"chunk_id": "local-1", "title": "K1 手册", "content": "本地内容"}],
            "web_search_docs": [{"title": "网页", "url": "https://example.com", "snippet": "网页内容"}],
        }
        node = RerankNode()

        diagnosis_docs = node._merge_multi_source__docs({**state, "mode": "diagnosis"})
        qa_docs = node._merge_multi_source__docs({**state, "mode": "qa"})

        self.assertEqual([doc["source"] for doc in diagnosis_docs], ["local"])
        self.assertEqual([doc["source"] for doc in qa_docs], ["local", "web"])


if __name__ == "__main__":
    unittest.main()
