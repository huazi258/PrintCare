import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from knowledge.api.import_router import create_app
from knowledge.core.deps import get_import_file_service
from knowledge.core.devices import UnsupportedDeviceError
from knowledge.processor.import_process.nodes.import_milvus import ImportMilvusNode, _MilvusSchemaBuilder
from knowledge.processor.import_process.nodes.item_name_recognition import ItemNameRecognitionNode
from knowledge.services.import_file_service import ImportFileService


class FakeImportFileService:
    def __init__(self):
        self.process_calls = []
        self.graph_calls = []

    def process_upload_file(self, file, device_id):
        self.process_calls.append((file.filename, device_id))
        return "task-k1", "C:/temporary/task-k1", "C:/temporary/task-k1/manual.md"

    def run_import_graph(self, task_id, file_dir, import_file_path, device_id):
        self.graph_calls.append((task_id, file_dir, import_file_path, device_id))


class FakeMilvusClient:
    def __init__(self):
        self.insert_calls = []

    def has_collection(self, **kwargs):
        return True

    def insert(self, collection_name, data):
        self.insert_calls.append((collection_name, copy.deepcopy(data)))
        return {"insert_count": len(data), "ids": [101]}


class FakeSchema:
    def __init__(self):
        self.fields = []

    def add_field(self, **kwargs):
        self.fields.append(kwargs)


class FakeSchemaClient:
    def __init__(self):
        self.create_schema_kwargs = None

    def create_schema(self, **kwargs):
        self.create_schema_kwargs = kwargs
        return FakeSchema()


class ImportDeviceAttributionTestCase(unittest.TestCase):
    def setUp(self):
        self.service = FakeImportFileService()
        self.app = create_app()
        self.app.dependency_overrides[get_import_file_service] = lambda: self.service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_upload_without_device_id_uses_the_legacy_k1_default(self):
        response = self.client.post(
            "/upload",
            files={"file": ("manual.md", b"# K1 manual", "text/markdown")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task_id"], "task-k1")
        self.assertEqual(self.service.process_calls, [("manual.md", "creality-k1")])
        self.assertEqual(self.service.graph_calls[-1][-1], "creality-k1")

    def test_upload_accepts_the_only_explicitly_supported_device_id(self):
        response = self.client.post(
            "/upload",
            data={"device_id": "creality-k1"},
            files={"file": ("manual.md", b"# K1 manual", "text/markdown")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.process_calls, [("manual.md", "creality-k1")])
        self.assertEqual(self.service.graph_calls[-1][-1], "creality-k1")

    def test_unsupported_device_is_rejected_before_any_upload_or_task_call(self):
        response = self.client.post(
            "/upload",
            data={"device_id": "creality-k1-max"},
            files={"file": ("manual.md", b"# K1 Max manual", "text/markdown")},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("仅支持 Creality K1", response.json()["detail"])
        self.assertEqual(self.service.process_calls, [])
        self.assertEqual(self.service.graph_calls, [])

    def test_service_rejects_unsupported_devices_before_its_first_side_effect(self):
        service = ImportFileService()
        with patch.object(service, "_save_upload_file_to_local") as save_local, patch(
            "knowledge.services.import_file_service.add_running_task"
        ) as add_task:
            with self.assertRaises(UnsupportedDeviceError):
                service.process_upload_file(Mock(), "creality-k1-max")

        save_local.assert_not_called()
        add_task.assert_not_called()

    def test_service_passes_canonical_device_fields_into_the_graph_state(self):
        service = ImportFileService()
        graph = Mock()
        graph.stream.return_value = iter([{"entry_node": {}}])

        with patch("knowledge.services.import_file_service.kb_import_graph_app", graph), patch(
            "knowledge.services.import_file_service.update_task_status"
        ) as update_status:
            service.run_import_graph("task-k1", "C:/temporary/task-k1", "C:/temporary/task-k1/manual.md", "creality-k1")

        state = graph.stream.call_args.args[0]
        self.assertEqual(state["device_id"], "creality-k1")
        self.assertEqual(state["device_model"], "Creality K1")
        update_status.assert_any_call("task-k1", "processing")
        update_status.assert_any_call("task-k1", "completed")

    def test_explicit_k1_bypasses_llm_recognition_and_sets_chunk_attribution(self):
        node = ItemNameRecognitionNode()
        state = {
            "file_title": "K1 service manual",
            "device_id": "creality-k1",
            "device_model": "forged display name",
            "chunks": [{"content": "maintenance instructions"}],
        }

        with patch.object(node, "_recognition_name") as recognition, patch.object(
            node, "_embedding_item_name", return_value=([0.1], {1: 0.2})
        ), patch.object(node, "_insert_milvus") as insert:
            result = node.process(state)

        recognition.assert_not_called()
        insert.assert_called_once()
        self.assertEqual(result["item_name"], "Creality K1")
        self.assertEqual(result["device_model"], "Creality K1")
        self.assertEqual(result["chunks"][0]["device_id"], "creality-k1")
        self.assertEqual(result["chunks"][0]["device_model"], "Creality K1")
        self.assertEqual(result["chunks"][0]["item_name"], "Creality K1")

    def test_milvus_insert_receives_device_attribution_without_a_schema_change(self):
        milvus = FakeMilvusClient()
        node = ImportMilvusNode()
        state = {
            "chunks": [{
                "content": "maintenance instructions",
                "title": "Maintenance",
                "parent_title": "Manual",
                "file_title": "K1 service manual",
                "item_name": "Creality K1",
                "device_id": "creality-k1",
                "device_model": "Creality K1",
                "dense_vector": [0.1],
                "sparse_vector": {1: 0.2},
            }]
        }

        with patch(
            "knowledge.processor.import_process.nodes.import_milvus.StorageClients.get_milvus_client",
            return_value=milvus,
        ), patch(
            "knowledge.processor.import_process.nodes.import_milvus.get_config",
            return_value=SimpleNamespace(chunks_collection="chunks"),
        ):
            result = node.process(state)

        self.assertEqual(milvus.insert_calls[0][0], "chunks")
        inserted_chunk = milvus.insert_calls[0][1][0]
        self.assertEqual(inserted_chunk["device_id"], "creality-k1")
        self.assertEqual(inserted_chunk["device_model"], "Creality K1")
        self.assertEqual(inserted_chunk["item_name"], "Creality K1")
        self.assertEqual(result["chunks"][0]["chunk_id"], 101)

    def test_new_chunk_collection_keeps_dynamic_fields_enabled(self):
        client = FakeSchemaClient()

        _MilvusSchemaBuilder.build(client, dim=1024)

        self.assertEqual(client.create_schema_kwargs, {"enable_dynamic_field": True})


if __name__ == "__main__":
    unittest.main()
