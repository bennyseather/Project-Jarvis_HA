import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jarvis.homeassistant.action_audit import SQLiteConfirmedActionAuditStore
from jarvis.homeassistant.action_gateway import ConfirmedHomeAssistantActionGateway
from jarvis.homeassistant.capability_gateway import HomeAssistantCapabilityGateway
from jarvis.homeassistant.pending_actions import PendingActionStore
from jarvis.homeassistant.risk_policy import HomeAssistantRiskPolicy
from jarvis.models.home_assistant_gateway import (
    HomeAssistantActionProposal, HomeAssistantCapabilityCatalog, HomeAssistantServiceDefinition,
)


class Client:
    def __init__(self, fail=False):
        self.fail = fail

    async def call_service(self, *args):
        if self.fail:
            raise RuntimeError("service unavailable")


class ConfirmedActionAuditTests(unittest.IsolatedAsyncioTestCase):
    def _gateway(self, store, client):
        catalog = HomeAssistantCapabilityCatalog(
            (HomeAssistantServiceDefinition("light", "turn_on", ("brightness",)),), frozenset({"light.blocks"})
        )
        return ConfirmedHomeAssistantActionGateway(
            HomeAssistantCapabilityGateway(catalog),
            HomeAssistantRiskPolicy({"light.turn_on"}, allowed_entities={"light.blocks"}),
            PendingActionStore(lambda: datetime(2026, 7, 26, tzinfo=timezone.utc)), client, store,
        )

    async def test_records_only_bounded_confirmed_action_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteConfirmedActionAuditStore(Path(directory) / "jarvis.sqlite3")
            try:
                gateway = self._gateway(store, Client())
                action = HomeAssistantActionProposal("light", "turn_on", ("light.blocks",),
                                                     service_data={"brightness": 50}, summary="private request")
                pending = gateway.request(action)
                self.assertEqual((await gateway.confirm(pending["token"], action))["status"], "success")
                record = store.recent()[0]
                self.assertEqual((record.domain, record.service, record.entity_ids, record.outcome),
                                 ("light", "turn_on", ("light.blocks",), "success"))
                self.assertNotIn("private request", str(record))
                self.assertNotIn("brightness", str(record))
            finally:
                store.close()

    async def test_records_failure_and_enforces_query_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteConfirmedActionAuditStore(Path(directory) / "jarvis.sqlite3")
            try:
                gateway = self._gateway(store, Client(fail=True))
                action = HomeAssistantActionProposal("light", "turn_on", ("light.blocks",))
                pending = gateway.request(action)
                result = await gateway.confirm(pending["token"], action)
                self.assertEqual(result["status"], "unavailable")
                record = store.recent()[0]
                self.assertEqual((record.outcome, record.reason_code),
                                 ("unavailable", "home_assistant_service_failed"))
                with self.assertRaises(ValueError):
                    store.recent(51)
            finally:
                store.close()
