import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bson import ObjectId

from knowledge.processor.query_process.nodes.answer_output import AnswerOutputNode
from knowledge.processor.query_process.nodes.item_name_confirm import (
    ItemNameAligner,
    ItemNameConfirmNode,
    ItemNameExtractor,
)
from knowledge.services.query_service import QueryService
from knowledge.utils import mongo_history_util, task_util


class FakeCursor:
    def __init__(self, records):
        self.records = list(records)

    def sort(self, field, direction):
        self.records.sort(key=lambda record: record[field], reverse=direction < 0)
        return self

    def limit(self, count):
        self.records = self.records[:count]
        return self

    def __iter__(self):
        return iter(self.records)


class FakeHistoryCollection:
    def __init__(self, records):
        self.records = list(records)
        self.update_filter = None
        self.update_document = None

    def find(self, query):
        return FakeCursor(
            record
            for record in self.records
            if record.get("session_id") == query["session_id"]
            and record.get("visitor_id") == query["visitor_id"]
        )

    def update_many(self, query, update):
        self.update_filter = query
        self.update_document = update
        return SimpleNamespace(modified_count=1)

    def insert_one(self, document):
        self.records.append(dict(document))
        return SimpleNamespace(inserted_id=ObjectId())


class HistoryAndQueryNodeTestCase(unittest.TestCase):
    def test_recent_messages_uses_recent_limit_but_returns_chronological_order(self):
        collection = FakeHistoryCollection(
            [
                {"session_id": "session", "visitor_id": "visitor-a", "text": "one", "ts": 1},
                {"session_id": "session", "visitor_id": "visitor-a", "text": "two", "ts": 2},
                {"session_id": "session", "visitor_id": "visitor-a", "text": "three", "ts": 3},
                {"session_id": "session", "visitor_id": "visitor-a", "text": "four", "ts": 4},
                {"session_id": "session", "visitor_id": "visitor-b", "text": "other visitor", "ts": 5},
            ]
        )
        with patch.object(mongo_history_util, "_get_collection", return_value=collection):
            self.assertEqual(mongo_history_util.get_recent_messages("session", "visitor-a", 2), [
                {"session_id": "session", "visitor_id": "visitor-a", "text": "three", "ts": 3},
                {"session_id": "session", "visitor_id": "visitor-a", "text": "four", "ts": 4},
            ])
            self.assertEqual([item["text"] for item in mongo_history_util.get_recent_messages("session", "visitor-a", 10)], [
                "one", "two", "three", "four"
            ])
            self.assertEqual(mongo_history_util.get_recent_messages("session", "visitor-b", 10)[0]["text"], "other visitor")
            self.assertEqual(mongo_history_util.get_recent_messages("missing", "visitor-a", 10), [])
            self.assertEqual(mongo_history_util.get_recent_messages("session", "", 10), [])

    def test_query_service_preserves_history_order(self):
        records = [
            {"_id": "first", "session_id": "session", "role": "user", "text": "old", "ts": 1},
            {"_id": "second", "session_id": "session", "role": "assistant", "text": "new", "ts": 2},
        ]
        with patch("knowledge.services.query_service.get_recent_messages", return_value=records) as get_recent:
            history = QueryService().get_history("session", "visitor-a", 10)
        get_recent.assert_called_once_with("session", "visitor-a", 10)
        self.assertEqual([item["text"] for item in history], ["old", "new"])

    def test_query_service_returns_sources_saved_with_the_matching_assistant_message(self):
        sources = [{
            "source_type": "web",
            "source_id": "https://example.test/k1",
            "excerpt": "网页资料",
            "url": "https://example.test/k1",
        }]
        records = [
            {"_id": "user", "session_id": "session", "role": "user", "text": "问题", "ts": 1},
            {
                "_id": "assistant", "session_id": "session", "role": "assistant", "text": "回答",
                "sources": sources, "ts": 2,
            },
        ]
        with patch("knowledge.services.query_service.get_recent_messages", return_value=records):
            history = QueryService().get_history("session", "visitor-a", 10)

        self.assertEqual(history[0]["sources"], [])
        self.assertEqual(history[1]["sources"], sources)

    def test_new_history_message_persists_visitor_ownership(self):
        collection = FakeHistoryCollection([])
        with patch.object(mongo_history_util, "_get_collection", return_value=collection):
            mongo_history_util.save_chat_message(
                "session", "visitor-a", "user", "K1 如何调平？"
            )

        self.assertEqual(collection.records[0]["session_id"], "session")
        self.assertEqual(collection.records[0]["visitor_id"], "visitor-a")

    def test_assistant_history_persists_only_its_own_structured_sources(self):
        collection = FakeHistoryCollection([])
        sources = [{
            "source_type": "local",
            "source_id": "chunk:101",
            "title": "Creality K1 用户手册",
            "excerpt": "热床调平说明",
        }]
        with patch.object(mongo_history_util, "_get_collection", return_value=collection):
            mongo_history_util.save_chat_message(
                "session", "visitor-a", "assistant", "回答", sources=sources
            )

        self.assertEqual(collection.records[0]["sources"], sources)

    def test_item_name_backfill_only_targets_empty_or_missing_item_names(self):
        collection = FakeHistoryCollection([])
        missing_id = ObjectId()
        empty_id = ObjectId()
        existing_id = ObjectId()
        with patch.object(mongo_history_util, "_get_collection", return_value=collection):
            count = mongo_history_util.update_message_item_names(
                [missing_id, str(empty_id), missing_id, "not-an-object-id"],
                ["RS PRO RS-12"],
            )

        self.assertEqual(count, 1)
        self.assertEqual(collection.update_document, {"$set": {"item_names": ["RS PRO RS-12"]}})
        self.assertEqual(collection.update_filter["_id"]["$in"], [missing_id, empty_id])
        self.assertEqual(
            collection.update_filter["$or"],
            [{"item_names": {"$exists": False}}, {"item_names": []}],
        )
        self.assertNotIn(existing_id, collection.update_filter["_id"]["$in"])

    def test_item_name_backfill_failure_returns_without_raising(self):
        collection = FakeHistoryCollection([])
        collection.update_many = Mock(side_effect=RuntimeError("database unavailable"))
        with patch.object(mongo_history_util, "_get_collection", return_value=collection):
            self.assertEqual(
                mongo_history_util.update_message_item_names([ObjectId()], ["RS PRO RS-12"]),
                0,
            )

    def test_confirm_node_backfills_only_history_records_without_item_names(self):
        missing_id = ObjectId()
        existing_id = ObjectId()
        node = ItemNameConfirmNode()
        node._item_name_extractor = Mock(return_value=None)
        node._item_name_extractor.extract_item_name.return_value = {
            "item_names": ["RS-12"],
            "rewritten_query": "RS-12 question",
        }
        node._item_name_aligner = Mock()
        node._item_name_aligner.match_align_filter.return_value = (["RS PRO RS-12"], [])
        history = [
            {"_id": missing_id, "role": "user", "text": "old", "item_names": []},
            {"_id": existing_id, "role": "assistant", "text": "new", "item_names": ["existing"]},
        ]

        with patch(
            "knowledge.processor.query_process.nodes.item_name_confirm.get_recent_messages",
            return_value=history,
        ), patch(
            "knowledge.processor.query_process.nodes.item_name_confirm.update_message_item_names"
        ) as backfill:
            state = node.process({"original_query": "question", "session_id": "session"})

        self.assertEqual(state["history"], history)
        node._item_name_extractor.extract_item_name.assert_called_once_with(
            "question", "user:old\nassistant:new\n"
        )
        backfill.assert_called_once_with([str(missing_id)], ["RS PRO RS-12"])

    def test_reranked_doc_metadata_formatting_and_budget(self):
        node = AnswerOutputNode()
        documents = [
            {
                "content": "local content",
                "source": "local",
                "chunk_id": "chunk-1",
                "title": "Local title",
                "score": 0.9,
            },
            {
                "content": "web content",
                "source": "web",
                "url": "https://example.test/source",
                "title": "Web title",
                "score": "0.25",
            },
            {"content": "metadata-free", "source": None, "url": None, "score": "invalid"},
        ]
        formatted, remaining = node._format_reranked_docs(documents, 1_000)
        expected = (
            "[1] [source=local] [chunk_id=chunk-1] [title=Local title] [score=0.9000]\nlocal content\n\n"
            "[2] [source=web] [url=https://example.test/source] [title=Web title] [score=0.2500]\nweb content\n\n"
            "[3]\nmetadata-free"
        )
        self.assertEqual(formatted, expected)
        self.assertEqual(remaining, 1_000 - len(expected))

        first_only, remaining = node._format_reranked_docs(documents, len(expected.split("\n\n")[0]))
        self.assertEqual(first_only, expected.split("\n\n")[0])
        self.assertEqual(remaining, 0)
        self.assertEqual(node._format_reranked_docs([], 10), ("", 10))
        self.assertEqual(node._format_reranked_docs(None, 10), ("", 10))

    def test_auxiliary_logger_paths_do_not_raise_attribute_error(self):
        extractor = ItemNameExtractor()
        llm = Mock()
        llm.invoke.return_value = SimpleNamespace(content="not-json")
        with patch(
            "knowledge.processor.query_process.nodes.item_name_confirm.AIClients.get_llm_openai",
            return_value=llm,
        ):
            result = extractor.extract_item_name("question", "")
        self.assertEqual(result, {"item_names": [], "rewritten_query": "question"})

        aligner = ItemNameAligner()
        with patch(
            "knowledge.processor.query_process.nodes.item_name_confirm.StorageClients.get_milvus_client",
            return_value=None,
        ):
            self.assertEqual(aligner._match_vector(["RS-12"]), [])

    def test_streaming_answer_is_available_from_task_status_result(self):
        task_util._tasks_result.clear()
        node = AnswerOutputNode()
        llm = Mock()
        llm.stream.return_value = [
            SimpleNamespace(content="第一段"),
            SimpleNamespace(content="第二段"),
        ]
        state = {
            "task_id": "stream-task",
            "session_id": "stream-session",
            "visitor_id": "visitor-a",
            "is_stream": True,
            "original_query": "K1 如何清洁平台？",
            "reranked_docs": [{
                "content": "使用无绒布清洁打印平台。",
                "source_type": "local",
                "source_id": "chunk:101",
                "file_title": "Creality K1 用户手册",
            }],
        }

        with patch(
            "knowledge.processor.query_process.nodes.answer_output.AIClients.get_llm_openai",
            return_value=llm,
        ), patch(
            "knowledge.processor.query_process.nodes.answer_output.save_chat_message"
        ) as save_history, patch(
            "knowledge.processor.query_process.nodes.answer_output.push_sse_event"
        ) as push_event:
            result = node.process(state)

        self.assertEqual(result["answer"], "第一段第二段")
        self.assertEqual(task_util.get_task_result("stream-task", "answer"), "第一段第二段")
        expected_sources = [{
            "source_type": "local",
            "source_id": "chunk:101",
            "title": "Creality K1 用户手册",
            "excerpt": "使用无绒布清洁打印平台。",
        }]
        self.assertEqual(task_util.get_task_result("stream-task", "sources"), expected_sources)
        self.assertEqual(save_history.call_count, 2)
        self.assertTrue(all(call.kwargs["visitor_id"] == "visitor-a" for call in save_history.call_args_list))
        self.assertEqual(save_history.call_args_list[-1].kwargs["sources"], expected_sources)
        push_event.assert_any_call(
            "stream-task",
            "final",
            {"answer": "第一段第二段", "sources": expected_sources},
        )

    def test_context_sources_exclude_docs_outside_budget_or_without_real_identifiers(self):
        node = AnswerOutputNode()
        selected = {
            "content": "selected local excerpt",
            "source_type": "local",
            "source_id": "chunk:101",
            "file_title": "K1 手册",
            "title": "调平",
        }
        excluded = {
            "content": "this document is outside the prompt budget",
            "source_type": "web",
            "source_id": "https://example.test/outside",
            "url": "https://example.test/outside",
        }
        untraceable = {"content": "untraceable local document", "source_type": "local"}

        first_entry, _ = node._format_reranked_docs([selected], 10_000)
        context, _, sources = node._format_context_sources(
            [selected, excluded, untraceable], len(first_entry)
        )

        self.assertEqual(context, first_entry)
        self.assertEqual(sources, [{
            "source_type": "local",
            "source_id": "chunk:101",
            "title": "K1 手册",
            "excerpt": "selected local excerpt",
            "section_title": "调平",
        }])


if __name__ == "__main__":
    unittest.main()
