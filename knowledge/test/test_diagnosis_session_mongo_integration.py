"""Opt-in integration coverage for PyMongo's naive UTC lease datetimes.

Set ``PRINTCARE_RUN_MONGO_INTEGRATION=1`` only with an isolated test database
configured through the normal Mongo settings.  The test creates and removes a
uniquely named collection; it never uses the production diagnosis collection.
"""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4

from knowledge.schema.diagnosis_schema import DiagnosisStartRequest
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils.diagnosis_session_util import (
    DiagnosisSessionConflictError,
    DiagnosisSessionRepository,
)


@unittest.skipUnless(
    os.getenv("PRINTCARE_RUN_MONGO_INTEGRATION") == "1",
    "set PRINTCARE_RUN_MONGO_INTEGRATION=1 to run against an isolated MongoDB database",
)
class DiagnosisSessionMongoIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            database = StorageClients.get_mongo_db()
            database.command("ping")
        except Exception as exc:  # pragma: no cover - depends on local infrastructure
            raise unittest.SkipTest(f"MongoDB 不可用: {type(exc).__name__}") from exc
        cls.collection = database[f"diagnosis_session_integration_{uuid4().hex}"]
        cls.repository = DiagnosisSessionRepository(collection=cls.collection)

    @classmethod
    def tearDownClass(cls):
        cls.collection.drop()

    def test_naive_pymongo_lease_is_reclaimed_once_after_expiry(self):
        created = self.repository.create_session(
            "integration-visitor",
            DiagnosisStartRequest(device_id="creality-k1", original_problem="首层无法粘附"),
            diagnosis_id=f"integration-{uuid4()}",
        )
        first = self.repository.claim_inference(
            created["diagnosis_id"],
            "integration-visitor",
            "start:integration",
            expected_revision=0,
            task_id="active-task",
        )
        self.assertIsNone(first.session["execution"]["expires_at"].tzinfo)

        duplicate = self.repository.claim_inference(
            created["diagnosis_id"],
            "integration-visitor",
            "start:integration",
            expected_revision=0,
            task_id="duplicate-task",
        )
        self.assertTrue(duplicate.running)
        self.assertEqual(duplicate.active_task_id, "active-task")

        self.collection.update_one(
            {"diagnosis_id": created["diagnosis_id"]},
            {"$set": {"execution.expires_at": datetime.utcnow() - timedelta(seconds=1)}},
        )

        def reclaim(request_id):
            try:
                return self.repository.claim_inference(
                    created["diagnosis_id"],
                    "integration-visitor",
                    request_id,
                    expected_revision=0,
                )
            except DiagnosisSessionConflictError:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(reclaim, ["recover-a", "recover-b"]))

        self.assertEqual(sum(item == "conflict" for item in outcomes), 1)
        self.assertEqual(sum(item != "conflict" for item in outcomes), 1)
