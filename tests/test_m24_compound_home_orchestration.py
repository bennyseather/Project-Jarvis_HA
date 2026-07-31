import unittest
from datetime import datetime, timezone

from jarvis.homeassistant.compound_orchestration import (
    CompoundHomeOrchestrator,
    CompoundOrchestrationPolicy,
)
from jarvis.homeassistant.home_topology import HomeTopologyAssembler


STATES = [
    {"entity_id": "light.kitchen", "state": "on", "attributes": {"friendly_name": "Kitchen Light"}},
    {"entity_id": "light.hall", "state": "on", "attributes": {"friendly_name": "Hallway Light"}},
    {"entity_id": "light.office", "state": "on", "attributes": {"friendly_name": "Office Light"}},
    {"entity_id": "lock.front_door", "state": "unlocked", "attributes": {"friendly_name": "Front Door"}},
    {"entity_id": "cover.lounge", "state": "open", "attributes": {"friendly_name": "Lounge Blinds"}},
    {"entity_id": "binary_sensor.patio", "state": "off", "attributes": {"friendly_name": "Patio Door", "device_class": "door"}},
    {"entity_id": "vacuum.downstairs", "state": "docked", "attributes": {"friendly_name": "Downstairs Vacuum"}},
    {"entity_id": "scene.movie_mode", "state": "scening", "attributes": {"friendly_name": "Movie Mode"}},
    {"entity_id": "light.private", "state": "on", "attributes": {"friendly_name": "Private Light"}},
]
AREAS = [
    {"area_id": "kitchen", "name": "Kitchen", "floor_id": "downstairs"},
    {"area_id": "hall", "name": "Hallway", "floor_id": "downstairs"},
    {"area_id": "office", "name": "Office", "floor_id": "upstairs"},
    {"area_id": "entry", "name": "Entry", "floor_id": "downstairs"},
    {"area_id": "lounge", "name": "Lounge", "floor_id": "downstairs"},
    {"area_id": "patio", "name": "Patio", "floor_id": "downstairs"},
]
FLOORS = [
    {"floor_id": "downstairs", "name": "Downstairs"},
    {"floor_id": "upstairs", "name": "Upstairs"},
]
REGISTRY = [
    {"ei": "light.kitchen", "ai": "kitchen"},
    {"ei": "light.hall", "ai": "hall"},
    {"ei": "light.office", "ai": "office"},
    {"ei": "lock.front_door", "ai": "entry"},
    {"ei": "cover.lounge", "ai": "lounge"},
    {"ei": "binary_sensor.patio", "ai": "patio"},
    {"ei": "vacuum.downstairs", "ai": "hall"},
]


class Client:
    def __init__(self):
        self.states = [dict(item) for item in STATES]

    async def get_states(self):
        return self.states


class Gateway:
    def __init__(self):
        self.requested = []
        self.executed = []
        self.confirmed = []

    def request(self, proposal):
        self.requested.append(proposal)
        if proposal.domain == "lock":
            return {
                "status": "requires_confirmation",
                "token": "lock-confirmation",
                "summary": proposal.summary,
            }
        return {"status": "immediate_action", "summary": proposal.summary}

    async def execute_immediate(self, proposal):
        self.executed.append(proposal)
        return {
            "status": "success",
            "succeeded": proposal.entity_ids,
            "failed": (),
        }

    async def confirm(self, token, proposal):
        self.confirmed.append((token, proposal))
        return {"status": "success"}


class PartialGateway(Gateway):
    async def execute_immediate(self, proposal):
        self.executed.append(proposal)
        return {
            "status": "success",
            "succeeded": proposal.entity_ids[:1],
            "failed": proposal.entity_ids[1:],
        }


class M24CompoundHomeOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        permitted = {item["entity_id"] for item in STATES} - {"light.private"}
        actionable = permitted - {"binary_sensor.patio"}
        self.client = Client()
        self.gateway = Gateway()
        self.assembler = HomeTopologyAssembler(
            AREAS, FLOORS, REGISTRY, [], permitted, actionable,
            maximum_entities=50,
        )
        self.engine = CompoundHomeOrchestrator(
            self.client,
            self.assembler,
            self.gateway,
            CompoundOrchestrationPolicy(),
            clock=lambda: datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        )

    def test_policy_is_bounded_and_validated(self):
        policy = CompoundOrchestrationPolicy.from_config({
            "maximum_actions": 8,
            "confirmation_ttl_seconds": 120,
        })
        self.assertEqual(policy.maximum_actions, 8)
        with self.assertRaises(ValueError):
            CompoundOrchestrationPolicy.from_config({"maximum_actions": 11})
        with self.assertRaises(ValueError):
            CompoundOrchestrationPolicy.from_config({"enabled": "yes"})

    async def test_parallel_actions_are_decomposed_and_executed(self):
        result = await self.engine.handle(
            "Turn off the kitchen light and close the lounge blinds", "one"
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(self.gateway.executed), 2)
        self.assertEqual(
            {(item.domain, item.service) for item in self.gateway.executed},
            {("light", "turn_off"), ("cover", "close_cover")},
        )

    async def test_then_creates_a_later_sequence(self):
        result = await self.engine.handle(
            "Turn off the kitchen light, then activate movie mode", "one"
        )
        self.assertEqual(result["succeeded_steps"], ("step-1", "step-2"))
        self.assertEqual(
            [(item.domain, item.service) for item in self.gateway.executed],
            [("light", "turn_off"), ("scene", "turn_on")],
        )
        self.gateway.executed.clear()
        movie = await self.engine.handle(
            "Close the lounge blinds, then turn on movie mode", "movie"
        )
        self.assertEqual(movie["status"], "success")
        self.assertEqual(self.gateway.executed[-1].domain, "scene")

    async def test_highest_risk_produces_one_compound_confirmation(self):
        result = await self.engine.handle(
            "Turn off the kitchen light and lock the front door", "one"
        )
        self.assertEqual(result["status"], "requires_confirmation")
        self.assertEqual(result["action_payload"]["kind"], "compound_plan")
        self.assertEqual(self.gateway.executed, [])
        confirmed = await self.engine.confirm(result["token"], result["action_payload"])
        self.assertEqual(confirmed["status"], "success")
        self.assertEqual(len(self.gateway.executed), 1)
        self.assertEqual(self.gateway.confirmed[0][0], "lock-confirmation")
        repeated = await self.engine.confirm(result["token"], result["action_payload"])
        self.assertEqual(repeated["status"], "forbidden")

    async def test_condition_is_rechecked_immediately_before_execution(self):
        result = await self.engine.handle(
            "If the patio door is closed, start the downstairs vacuum", "one"
        )
        self.assertEqual(result["skipped_steps"], ())
        self.assertEqual(self.gateway.executed[0].service, "start")
        self.client.states[5] = {
            **self.client.states[5],
            "state": "on",
        }
        skipped = await self.engine.handle(
            "If the patio door is closed, start the downstairs vacuum", "two"
        )
        self.assertEqual(skipped["skipped_steps"], ("step-1",))

    async def test_except_removes_the_resolved_target(self):
        result = await self.engine.handle(
            "Turn off everything except the hallway light and close the lounge blinds",
            "one",
        )
        self.assertEqual(result["status"], "success")
        lights = next(item for item in self.gateway.executed if item.domain == "light")
        self.assertEqual(lights.entity_ids, ("light.kitchen", "light.office"))
        self.assertNotIn("light.private", lights.entity_ids)

    async def test_unresolved_or_oversized_plans_are_rejected_before_execution(self):
        unresolved = await self.engine.handle(
            "Turn off the imaginary light and lock the front door", "one"
        )
        self.assertEqual(unresolved["status"], "clarification_required")
        self.assertEqual(self.gateway.executed, [])
        limited = CompoundHomeOrchestrator(
            self.client, self.assembler, self.gateway,
            CompoundOrchestrationPolicy(maximum_actions=2),
        )
        oversized = await limited.handle(
            "Turn off everything and close the lounge blinds", "two"
        )
        self.assertEqual(oversized["status"], "clarification_required")

    async def test_partial_device_outcomes_are_explicit(self):
        gateway = PartialGateway()
        engine = CompoundHomeOrchestrator(
            self.client, self.assembler, gateway, CompoundOrchestrationPolicy()
        )
        result = await engine.handle(
            "Turn off downstairs lights and close the lounge blinds", "partial"
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("1 succeeded and 1 failed", result["message"])
        self.assertEqual(result["failed_steps"], ("step-1",))

    async def test_non_compound_request_falls_through(self):
        self.assertIsNone(
            await self.engine.handle("Turn off the kitchen light", "one")
        )

    async def test_new_plan_invalidates_an_earlier_compound_confirmation(self):
        first = await self.engine.handle(
            "Turn off the kitchen light and lock the front door", "one"
        )
        second = await self.engine.handle(
            "Turn off the office light and lock the front door", "one"
        )
        invalid = await self.engine.confirm(first["token"], first["action_payload"])
        self.assertEqual(invalid["status"], "forbidden")
        valid = await self.engine.confirm(second["token"], second["action_payload"])
        self.assertEqual(valid["status"], "success")

    def test_runtime_and_addon_package_include_m24(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        application = (root / "src/jarvis/core/application.py").read_text()
        bridge = (root / "src/jarvis/homeassistant/conversation_bridge.py").read_text()
        self.assertIn("compound_orchestration.handle", application)
        self.assertIn('payload.get("kind") == "compound_plan"', bridge)
        addon = root / "home_assistant/addons/jarvis/app/src/jarvis"
        self.assertTrue((addon / "homeassistant/compound_orchestration.py").exists())
        self.assertTrue((addon / "models/compound_orchestration.py").exists())


if __name__ == "__main__":
    unittest.main()
