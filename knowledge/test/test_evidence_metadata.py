import unittest
from unittest.mock import Mock, patch

from knowledge.processor.query_process.nodes.answer_output import AnswerOutputNode
from knowledge.processor.query_process.nodes.hyde_search import HyDeSearchNode
from knowledge.processor.query_process.nodes.rerank import RerankNode
from knowledge.processor.query_process.nodes.rrf import RrfNode
from knowledge.processor.query_process.nodes.vector_search import VectorSearchNode


K1_CHUNK = {
    "chunk_id": 101,
    "content": "K1 热床调平说明",
    "title": "调平",
    "file_title": "Creality K1 用户手册",
    "item_name": "Creality K1",
    "device_id": "creality-k1",
    "device_model": "Creality K1",
}


class EvidenceMetadataTestCase(unittest.TestCase):
    @staticmethod
    def _search_state():
        return {
            "rewritten_query": "如何调平热床？",
            "item_names": ["Creality K1"],
            "device_id": "creality-k1",
        }

    @staticmethod
    def _search_hit():
        return {"entity": dict(K1_CHUNK), "distance": 0.9}

    def test_vector_and_hyde_request_all_available_evidence_fields(self):
        with patch(
            "knowledge.processor.query_process.nodes.vector_search.AIClients.get_bge_m3_client",
            return_value=object(),
        ), patch(
            "knowledge.processor.query_process.nodes.vector_search.StorageClients.get_milvus_client",
            return_value=object(),
        ), patch(
            "knowledge.processor.query_process.nodes.vector_search.generate_bge_m3_hybrid_vectors",
            return_value={"dense": [[0.1]], "sparse": [{1: 0.2}]},
        ), patch(
            "knowledge.processor.query_process.nodes.vector_search.execute_hybrid_search_query",
            return_value=[[self._search_hit()]],
        ) as vector_search:
            vector_state = VectorSearchNode().process(self._search_state())

        hyde_node = HyDeSearchNode()
        hyde_node._generate_by_document = Mock(return_value="K1 假设文档")
        with patch(
            "knowledge.processor.query_process.nodes.hyde_search.AIClients.get_bge_m3_client",
            return_value=object(),
        ), patch(
            "knowledge.processor.query_process.nodes.hyde_search.StorageClients.get_milvus_client",
            return_value=object(),
        ), patch(
            "knowledge.processor.query_process.nodes.hyde_search.generate_bge_m3_hybrid_vectors",
            return_value={"dense": [[0.1]], "sparse": [{1: 0.2}]},
        ), patch(
            "knowledge.processor.query_process.nodes.hyde_search.execute_hybrid_search_query",
            return_value=[[self._search_hit()]],
        ) as hyde_search:
            hyde_state = hyde_node.process(self._search_state())

        expected_fields = [
            "chunk_id", "content", "title", "file_title", "item_name", "device_id", "device_model",
        ]
        self.assertEqual(vector_search.call_args.kwargs["output_fields"], expected_fields)
        self.assertEqual(hyde_search.call_args.kwargs["output_fields"], expected_fields)
        self.assertEqual(vector_state["embedding_chunks"][0]["entity"], K1_CHUNK)
        self.assertEqual(hyde_state["hyde_embedding_chunks"][0]["entity"], K1_CHUNK)

    def test_rrf_keeps_complete_metadata_and_same_chunk_identity_across_paths(self):
        state = {
            "embedding_chunks": [self._search_hit()],
            "hyde_embedding_chunks": [self._search_hit()],
        }

        result = RrfNode().process(state)

        self.assertEqual(result["rrf_chunks"], [K1_CHUNK])

    def test_rerank_local_evidence_keeps_actual_source_and_device_fields(self):
        node = RerankNode()
        state = {"mode": "diagnosis", "rrf_chunks": [dict(K1_CHUNK)]}
        with patch.object(
            node,
            "_rerank_merged_docs",
            side_effect=lambda _query, docs: [{**doc, "score": 0.88} for doc in docs],
        ):
            result = node.process({**state, "original_query": "调平"})

        evidence = result["reranked_docs"][0]
        self.assertEqual(evidence["source"], "local")
        self.assertEqual(evidence["source_type"], "local")
        self.assertEqual(evidence["source_id"], "chunk:101")
        for field in ("chunk_id", "file_title", "item_name", "device_id", "device_model"):
            self.assertEqual(evidence[field], K1_CHUNK[field])
        self.assertEqual(evidence["score"], 0.88)

    def test_web_evidence_uses_its_actual_url_as_source_id(self):
        node = RerankNode()
        docs = node._merge_multi_source__docs(
            {
                "mode": "qa",
                "web_search_docs": [
                    {"title": "官方页面", "url": "https://example.test/k1", "snippet": "网页资料"}
                ],
            }
        )

        self.assertEqual(docs[0]["source"], "web")
        self.assertEqual(docs[0]["source_type"], "web")
        self.assertEqual(docs[0]["source_id"], "https://example.test/k1")
        self.assertEqual(docs[0]["url"], "https://example.test/k1")
        self.assertNotIn("chunk_id", docs[0])

    def test_missing_identifiers_and_file_fields_are_not_fabricated(self):
        node = RerankNode()
        docs = node._merge_multi_source__docs(
            {
                "mode": "qa",
                "rrf_chunks": [{"content": "无标识本地内容"}],
                "web_search_docs": [{"content": "无 URL 网页内容"}],
            }
        )

        local_doc, web_doc = docs
        self.assertIsNone(local_doc["source_id"])
        self.assertNotIn("chunk_id", local_doc)
        self.assertNotIn("file_title", local_doc)
        self.assertIsNone(web_doc["source_id"])
        self.assertNotIn("url", web_doc)

    def test_diagnosis_never_merges_injected_web_evidence(self):
        docs = RerankNode()._merge_multi_source__docs(
            {
                "mode": "diagnosis",
                "rrf_chunks": [dict(K1_CHUNK)],
                "web_search_docs": [{"url": "https://example.test/injected", "snippet": "不应混入"}],
            }
        )

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["source_type"], "local")

    def test_answer_prompt_formats_real_metadata_and_does_not_invent_citations(self):
        node = AnswerOutputNode()
        local_doc = RerankNode()._merge_multi_source__docs({"rrf_chunks": [dict(K1_CHUNK)]})[0]
        local_doc["score"] = 0.9
        web_doc = RerankNode()._merge_multi_source__docs(
            {"mode": "qa", "web_search_docs": [{"url": "https://example.test/k1", "snippet": "网页资料"}]}
        )[0]
        web_doc["score"] = 0.25

        formatted, _ = node._format_reranked_docs([local_doc, web_doc], 2_000)
        self.assertIn("[source=local] [source_id=chunk:101] [chunk_id=101]", formatted)
        self.assertIn("[file_title=Creality K1 用户手册]", formatted)
        self.assertIn("[device_id=creality-k1] [device_model=Creality K1] [score=0.9000]", formatted)
        self.assertIn("[source=web] [source_id=https://example.test/k1] [url=https://example.test/k1]", formatted)
        self.assertIn("[score=0.2500]", formatted)

        prompt = node._build_prompt({"original_query": "没有资料的问题", "reranked_docs": []})
        self.assertIn("无参考内容", prompt)
        self.assertNotIn("source_id=", prompt)


if __name__ == "__main__":
    unittest.main()
