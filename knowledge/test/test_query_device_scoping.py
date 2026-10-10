import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from knowledge.api.query_router import create_app
from knowledge.core.deps import get_query_service
from knowledge.processor.query_process.nodes.hyde_search import HyDeSearchNode
from knowledge.processor.query_process.nodes.item_name_confirm import ItemNameConfirmNode
from knowledge.processor.query_process.nodes.vector_search import VectorSearchNode
from knowledge.services.query_service import QueryService
from knowledge.utils.milvus_util import create_hybrid_search_requests


K1_DEVICE_ID = "creality-k1"
K1_ITEM_NAME = "Creality K1"
EXPECTED_EXPR = "device_id == {device_id} and item_name in {item_names}"
EXPECTED_PARAMS = {"device_id": K1_DEVICE_ID, "item_names": [K1_ITEM_NAME]}


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

    def get_answer(self, task_id):
        return "mock answer"


class QueryDeviceScopingTestCase(unittest.TestCase):
    def setUp(self):
        self.service = RecordingQueryService()
        self.app = create_app()
        self.app.dependency_overrides[get_query_service] = lambda: self.service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _query_payload(self, **overrides):
        payload = {"query": "如何调平热床？", "session_id": "session", "is_stream": False}
        payload.update(overrides)
        return payload

    def test_query_defaults_to_k1_and_passes_only_device_id_to_service(self):
        response = self.client.post("/query", json=self._query_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.run_calls[0][-2], K1_DEVICE_ID)

    def test_streaming_query_keeps_the_device_scope(self):
        response = self.client.post("/query", json=self._query_payload(is_stream=True))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task_id"], "task-1")
        self.assertEqual(self.service.run_calls[0][-2], K1_DEVICE_ID)

    def test_query_accepts_explicit_k1_and_rejects_unsupported_before_task_creation(self):
        accepted = self.client.post("/query", json=self._query_payload(device_id=K1_DEVICE_ID))
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(self.service.run_calls[0][-2], K1_DEVICE_ID)

        rejected = self.client.post("/query", json=self._query_payload(device_id="creality-k1-max"))
        self.assertEqual(rejected.status_code, 422)
        self.assertIn("仅支持 Creality K1", rejected.json()["detail"])
        self.assertEqual(self.service.created_task_ids, ["task-1"])
        self.assertEqual(len(self.service.run_calls), 1)

    def test_service_constructs_canonical_device_state(self):
        service = QueryService()
        with patch("knowledge.services.query_service.query_app.invoke") as invoke:
            service.run_query_graph("session", "task", "question", False)

        state = invoke.call_args.args[0]
        self.assertEqual(state["device_id"], K1_DEVICE_ID)
        self.assertEqual(state["device_model"], "Creality K1")
        self.assertEqual(state["item_names"], [K1_ITEM_NAME])

    def test_confirm_node_keeps_fixed_device_item_name_and_rewrite(self):
        node = ItemNameConfirmNode()
        node._item_name_extractor = Mock()
        node._item_name_extractor.extract_item_name.return_value = {
            "item_names": ["K1 Max"],
            "rewritten_query": "保留历史上下文的调平问题",
        }
        node._item_name_aligner = Mock()

        with patch(
            "knowledge.processor.query_process.nodes.item_name_confirm.get_recent_messages", return_value=[]
        ):
            state = node.process({
                "original_query": "热床怎么调平？",
                "session_id": "session",
                "device_id": K1_DEVICE_ID,
                "item_names": [K1_ITEM_NAME],
            })

        self.assertEqual(state["item_names"], [K1_ITEM_NAME])
        self.assertEqual(state["rewritten_query"], "保留历史上下文的调平问题")
        node._item_name_aligner.match_align_filter.assert_not_called()

    def test_hybrid_requests_apply_device_filter_to_dense_and_sparse_searches(self):
        requests = create_hybrid_search_requests(
            dense_vector=[0.1],
            sparse_vector={1: 0.2},
            expr=EXPECTED_EXPR,
            expr_params=EXPECTED_PARAMS,
        )

        self.assertEqual(len(requests), 2)
        for request in requests:
            self.assertEqual(request._expr, EXPECTED_EXPR)
            self.assertEqual(request._expr_params, EXPECTED_PARAMS)

    def _filtered_milvus_result(self, **kwargs):
        search_requests = kwargs["search_requests"]
        self.assertEqual(len(search_requests), 2)
        for request in search_requests:
            self.assertEqual(request._expr, EXPECTED_EXPR)
            self.assertEqual(request._expr_params, EXPECTED_PARAMS)

        mixed_device_hits = [
            {"entity": {"chunk_id": 1, "item_name": K1_ITEM_NAME, "device_id": K1_DEVICE_ID}},
            {"entity": {"chunk_id": 2, "item_name": K1_ITEM_NAME, "device_id": "creality-k1-max"}},
            {"entity": {"chunk_id": 3, "item_name": K1_ITEM_NAME}},
        ]
        return [[
            hit for hit in mixed_device_hits
            if hit["entity"].get("device_id") == K1_DEVICE_ID
        ]]

    def _state(self):
        return {
            "rewritten_query": "如何调平热床？",
            "item_names": [K1_ITEM_NAME],
            "device_id": K1_DEVICE_ID,
        }

    @patch("knowledge.processor.query_process.nodes.vector_search.execute_hybrid_search_query")
    @patch("knowledge.processor.query_process.nodes.vector_search.generate_bge_m3_hybrid_vectors")
    @patch("knowledge.processor.query_process.nodes.vector_search.StorageClients.get_milvus_client")
    @patch("knowledge.processor.query_process.nodes.vector_search.AIClients.get_bge_m3_client")
    def test_vector_search_filters_mixed_device_hits_at_milvus(
        self, get_embedding_client, get_milvus_client, generate_vectors, execute_search
    ):
        get_embedding_client.return_value = object()
        get_milvus_client.return_value = object()
        generate_vectors.return_value = {"dense": [[0.1]], "sparse": [{1: 0.2}]}
        execute_search.side_effect = self._filtered_milvus_result

        state = VectorSearchNode().process(self._state())

        self.assertEqual([hit["entity"]["chunk_id"] for hit in state["embedding_chunks"]], [1])
        self.assertEqual(execute_search.call_args.kwargs["output_fields"][-2:], ["device_id", "device_model"])

    @patch("knowledge.processor.query_process.nodes.hyde_search.execute_hybrid_search_query")
    @patch("knowledge.processor.query_process.nodes.hyde_search.generate_bge_m3_hybrid_vectors")
    @patch("knowledge.processor.query_process.nodes.hyde_search.StorageClients.get_milvus_client")
    @patch("knowledge.processor.query_process.nodes.hyde_search.AIClients.get_bge_m3_client")
    def test_hyde_search_filters_mixed_device_hits_at_milvus(
        self, get_embedding_client, get_milvus_client, generate_vectors, execute_search
    ):
        get_embedding_client.return_value = object()
        get_milvus_client.return_value = object()
        generate_vectors.return_value = {"dense": [[0.1]], "sparse": [{1: 0.2}]}
        execute_search.side_effect = self._filtered_milvus_result
        node = HyDeSearchNode()
        node._generate_by_document = Mock(return_value="假设性 K1 文档")

        state = node.process(self._state())

        self.assertEqual([hit["entity"]["chunk_id"] for hit in state["hyde_embedding_chunks"]], [1])
        self.assertEqual(execute_search.call_args.kwargs["output_fields"][-2:], ["device_id", "device_model"])

    @patch("knowledge.processor.query_process.nodes.vector_search.execute_hybrid_search_query", return_value=[[]])
    @patch("knowledge.processor.query_process.nodes.vector_search.generate_bge_m3_hybrid_vectors")
    @patch("knowledge.processor.query_process.nodes.vector_search.StorageClients.get_milvus_client")
    @patch("knowledge.processor.query_process.nodes.vector_search.AIClients.get_bge_m3_client")
    def test_no_match_does_not_retry_without_device_filter(
        self, get_embedding_client, get_milvus_client, generate_vectors, execute_search
    ):
        get_embedding_client.return_value = object()
        get_milvus_client.return_value = object()
        generate_vectors.return_value = {"dense": [[0.1]], "sparse": [{1: 0.2}]}

        state = VectorSearchNode().process(self._state())

        self.assertNotIn("embedding_chunks", state)
        self.assertEqual(execute_search.call_count, 1)


if __name__ == "__main__":
    unittest.main()
