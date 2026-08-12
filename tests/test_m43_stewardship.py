import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.homeassistant.stewardship import (
    SQLiteStewardshipStore,
    StewardshipController,
    StewardshipMode,
    StewardshipPolicy,
)
from jarvis.models.home_topology import HomeTopologyEntity, HomeTopologySnapshot


class Client:
    def __init__(self): self.states = []
    async def get_states(self): return self.states


class Assembler:
    def __init__(self, entities): self.entities = entities
    def assemble(self, states, captured_at=None):
        return HomeTopologySnapshot(captured_at, tuple(self.entities), {}, {}, {})


class Gateway:
    def __init__(self): self.executed = []
    def request(self, proposal): return {"status": "immediate_action"}
    async def execute_immediate(self, proposal):
        self.executed.append(proposal)
        return {"status": "success", "succeeded": proposal.entity_ids, "failed": ()}


class StewardshipTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 8, 12, 10, tzinfo=timezone.utc)
        self.store = SQLiteStewardshipStore(Path(self.temp.name) / "jarvis.db")
        self.entities = [
            HomeTopologyEntity("light.hall", "Hall", "light", "on", {}, action_allowed=True),
            HomeTopologyEntity("climate.lounge", "Lounge", "climate", "heat", {"temperature": 22}, action_allowed=True),
            HomeTopologyEntity("lock.front", "Front", "lock", "unlocked", {}, action_allowed=True),
        ]
        self.gateway = Gateway()
        self.controller = StewardshipController(Client(), Assembler(self.entities), self.gateway, self.store, StewardshipPolicy(), clock=lambda: self.now)

    def tearDown(self): self.store.close(); self.temp.cleanup()

    async def test_vacation_requires_confirmation_and_excludes_high_risk_domains(self):
        result = await self.controller.handle("I am travelling, activate vacation mode and keep the lights off and temperature at 20", "c1")
        self.assertEqual(result["status"], "requires_confirmation")
        self.assertIn("locks, alarms and cameras unchanged", result["summary"])
        confirmed = await self.controller.confirm(result["token"], result["action_payload"])
        self.assertEqual(confirmed["status"], "success")
        self.assertEqual([p.domain for p in self.gateway.executed], ["light", "climate"])
        self.assertEqual(self.store.active().name, "vacation")

    async def test_expiry_is_restart_safe_and_does_not_restore_devices(self):
        self.store.save(StewardshipMode("x", "away", self.now.isoformat(), (self.now - timedelta(seconds=1)).isoformat(), True, None, ()))
        result = await self.controller.reconcile()
        self.assertIn("expired", result["message"])
        self.assertIsNone(self.store.active())
        self.assertEqual(self.gateway.executed, [])

    async def test_manual_override_gets_grace_period(self):
        self.store.save(StewardshipMode("x", "away", self.now.isoformat(), None, True, None, ()))
        await self.controller.reconcile()
        self.entities[0] = HomeTopologyEntity("light.hall", "Hall", "light", "on", {}, action_allowed=True)
        self.gateway.executed.clear()
        await self.controller.reconcile()
        self.assertEqual(self.gateway.executed, [])

    def test_policy_validation(self):
        with self.assertRaises(ValueError): StewardshipPolicy.from_config({"reconciliation_seconds": 5})
