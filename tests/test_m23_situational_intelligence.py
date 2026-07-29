import unittest
from datetime import datetime, timezone

from jarvis.homeassistant.entity_reference_resolver import EntityReferenceResolver
from jarvis.homeassistant.home_topology import HomeTopologyAssembler
from jarvis.homeassistant.situational_intelligence import (
    SituationalIntelligencePolicy,
    WholeHomeSituationalIntelligence,
)
from jarvis.models.event_timeline import TimelineEvent
from jarvis.timeline.policy import EventTimelinePolicy
from jarvis.timeline.store import InMemoryTimelineStore


STATES = [
    {
        "entity_id": "light.blocks",
        "state": "on",
        "attributes": {"friendly_name": "Blocks"},
    },
    {
        "entity_id": "light.office",
        "state": "off",
        "attributes": {"friendly_name": "Office Main Light"},
    },
    {
        "entity_id": "switch.heater",
        "state": "on",
        "attributes": {"friendly_name": "Office Heater"},
    },
    {
        "entity_id": "binary_sensor.office_window",
        "state": "on",
        "attributes": {
            "friendly_name": "Office Window",
            "device_class": "window",
        },
    },
    {
        "entity_id": "sensor.panel_battery",
        "state": "15",
        "attributes": {
            "friendly_name": "Panel Battery",
            "device_class": "battery",
            "unit_of_measurement": "%",
        },
    },
    {
        "entity_id": "sensor.office_temperature",
        "state": "21.5",
        "attributes": {"friendly_name": "Office Temperature"},
    },
    {
        "entity_id": "light.private",
        "state": "on",
        "attributes": {"friendly_name": "Private"},
    },
]

AREAS = [
    {"area_id": "office", "name": "Upstairs Office", "floor_id": "upstairs"},
    {"area_id": "hall", "name": "Hall", "floor_id": "upstairs"},
]
FLOORS = [{"floor_id": "upstairs", "name": "Upstairs"}]
REGISTRY = [
    {"ei": "light.blocks", "ai": "office"},
    {"ei": "light.office", "ai": "office"},
    {"ei": "switch.heater", "ai": "office"},
    {"ei": "binary_sensor.office_window", "ai": "office"},
    {"ei": "sensor.office_temperature", "ai": "office"},
    {"ei": "sensor.panel_battery", "ai": "hall"},
]


class Client:
    def __init__(self, states=STATES):
        self.states = states
        self.calls = 0

    async def get_states(self):
        self.calls += 1
        return self.states


class Gateway:
    def __init__(self, result="immediate_action", failed=()):
        self.result = result
        self.failed = tuple(failed)
        self.proposals = []
        self.executed = []

    def request(self, proposal):
        self.proposals.append(proposal)
        if self.result == "requires_confirmation":
            return {
                "status": "requires_confirmation",
                "token": "one",
                "summary": proposal.summary,
            }
        return {"status": "immediate_action", "summary": proposal.summary}

    async def execute_immediate(self, proposal):
        self.executed.append(proposal)
        succeeded = tuple(
            entity_id for entity_id in proposal.entity_ids
            if entity_id not in self.failed
        )
        return {
            "status": "success",
            "message": f"Action completed for {len(succeeded)} devices.",
            "succeeded": succeeded,
            "failed": self.failed,
        }


class M23SituationalIntelligenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        permitted = {item["entity_id"] for item in STATES} - {"light.private"}
        self.assembler = HomeTopologyAssembler(
            AREAS,
            FLOORS,
            REGISTRY,
            [],
            permitted,
            {"light.blocks", "light.office", "switch.heater"},
            maximum_entities=50,
        )
        self.timeline = InMemoryTimelineStore(500)
        self.gateway = Gateway()
        self.engine = WholeHomeSituationalIntelligence(
            Client(),
            self.assembler,
            self.timeline,
            self.gateway,
            SituationalIntelligencePolicy(maximum_entities=50),
            clock=lambda: datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc),
        )

    def test_policy_bounds_are_validated(self):
        policy = SituationalIntelligencePolicy.from_config({
            "maximum_entities": 100,
            "maximum_details": 5,
            "maximum_timeline_results": 10,
            "low_battery_threshold": 25,
        })
        self.assertEqual(policy.maximum_details, 5)
        with self.assertRaises(ValueError):
            SituationalIntelligencePolicy.from_config({"maximum_details": 21})
        with self.assertRaises(ValueError):
            SituationalIntelligencePolicy.from_config({"enabled": "yes"})

    def test_topology_is_permitted_bounded_and_spatial(self):
        snapshot = self.assembler.assemble(STATES)
        ids = {item.entity_id for item in snapshot.entities}
        self.assertNotIn("light.private", ids)
        self.assertEqual(
            snapshot.floors["upstairs"],
            (
                "binary_sensor.office_window",
                "light.blocks",
                "light.office",
                "sensor.office_temperature",
                "sensor.panel_battery",
                "switch.heater",
            ),
        )
        blocks = snapshot.entity_map()["light.blocks"]
        self.assertEqual(blocks.area_name, "Upstairs Office")
        self.assertEqual(blocks.floor_name, "Upstairs")
        self.assertTrue(blocks.action_allowed)

    async def test_compound_area_floor_and_health_queries_use_friendly_names(self):
        office = await self.engine.handle(
            "Which lights in the upstairs office are on?", "one"
        )
        self.assertEqual(office["entity_ids"], ("light.blocks",))
        self.assertIn("Blocks is on", office["message"])
        floor = await self.engine.handle(
            "Are any windows upstairs open?", "one"
        )
        self.assertIn("Yes.", floor["message"])
        self.assertIn("Office Window", floor["message"])
        health = await self.engine.handle("Is everything okay?", "one")
        self.assertIn("Panel Battery is 15%", health["message"])
        self.assertNotIn("light.", health["message"])

    async def test_all_and_rest_followups_reuse_exact_spatial_scope(self):
        first = await self.engine.handle(
            "What is the state of all lights in the upstairs office?", "one"
        )
        self.assertIn("Blocks is on", first["message"])
        followup = await self.engine.handle("Are all of them on?", "one")
        self.assertIn("No. 1 of 2 lights", followup["message"])
        await self.engine.handle(
            "What is the state of all lights in the upstairs office?", "two"
        )
        rest = await self.engine.handle(
            "What about the rest of the devices there?", "two"
        )
        self.assertIn("Office Heater", rest["message"])
        self.assertNotIn("Blocks is", rest["message"])

    async def test_large_selection_is_summarized_not_rejected(self):
        many = [
            {
                "entity_id": f"sensor.item_{index}",
                "state": "on" if index % 2 else "off",
                "attributes": {"friendly_name": f"Item {index}"},
            }
            for index in range(30)
        ]
        registry = [
            {"ei": item["entity_id"], "ai": "office"} for item in many
        ]
        assembler = HomeTopologyAssembler(
            AREAS,
            FLOORS,
            registry,
            [],
            {item["entity_id"] for item in many},
            (),
            maximum_entities=50,
        )
        engine = WholeHomeSituationalIntelligence(
            Client(many),
            assembler,
            self.timeline,
            self.gateway,
            SituationalIntelligencePolicy(
                maximum_entities=50, maximum_details=5
            ),
        )
        result = await engine.handle(
            "What is the status of the upstairs office devices?", "one"
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("30 devices", result["message"])
        self.assertIn("30 sensors", result["message"])
        self.assertNotIn("Item 29 is", result["message"])

    async def test_temporal_query_uses_only_bounded_permitted_timeline(self):
        now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
        self.timeline.append("state_changed", "light.blocks", now, "off")
        self.timeline.append("state_changed", "light.private", now, "off")
        for index in range(60):
            self.timeline.append(
                "state_changed", "sensor.panel_battery", now, str(index)
            )
        await self.engine.handle(
            "What is the state of the upstairs office lights?", "one"
        )
        result = await self.engine.handle(
            "What changed there recently?", "one"
        )
        self.assertIn("Blocks changed to off", result["message"])
        self.assertNotIn("Private", result["message"])

    async def test_exact_filtered_action_uses_existing_gateway(self):
        result = await self.engine.handle(
            "Turn off all lights that are still on in the upstairs office",
            "one",
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(self.gateway.executed), 1)
        self.assertEqual(
            self.gateway.executed[0].entity_ids, ("light.blocks",)
        )
        self.assertEqual(self.gateway.executed[0].service, "turn_off")

    async def test_domain_actions_exclude_aggregate_group_helpers(self):
        states = [
            *STATES,
            {
                "entity_id": "light.upstairs_office_lights",
                "state": "unavailable",
                "attributes": {
                    "friendly_name": "Upstairs Office Lights",
                },
            },
        ]
        assembler = HomeTopologyAssembler(
            AREAS,
            FLOORS,
            [*REGISTRY, {"ei": "light.upstairs_office_lights", "ai": "office"}],
            [],
            {item["entity_id"] for item in states} - {"light.private"},
            {
                "light.blocks",
                "light.office",
                "light.upstairs_office_lights",
            },
            maximum_entities=50,
        )
        gateway = Gateway()
        engine = WholeHomeSituationalIntelligence(
            Client(states),
            assembler,
            self.timeline,
            gateway,
            SituationalIntelligencePolicy(maximum_entities=50),
        )
        result = await engine.handle(
            "Turn off all lights that are still on in the upstairs office",
            "one",
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(gateway.executed[0].entity_ids, ("light.blocks",))

    async def test_action_records_timeline_and_back_followup_scope(self):
        first = await self.engine.handle(
            "Turn off all lights that are still on in the upstairs office",
            "one",
            source_id="panel",
        )
        self.assertEqual(first["status"], "success")
        second = await self.engine.handle(
            "Turn back on", "two", source_id="panel"
        )
        self.assertEqual(second["status"], "success")
        self.assertEqual(self.gateway.executed[-1].entity_ids, ("light.blocks",))
        self.assertEqual(self.gateway.executed[-1].service, "turn_on")
        third = await self.engine.handle(
            "Turn them off", "three", source_id="panel"
        )
        self.assertEqual(third["status"], "success")
        self.assertEqual(self.gateway.executed[-1].entity_ids, ("light.blocks",))
        self.assertEqual(self.gateway.executed[-1].service, "turn_off")
        recent = await self.engine.handle(
            "What changed in the upstairs office recently?",
            "four",
            source_id="panel",
        )
        self.assertIn("Blocks changed to off", recent["message"])
        self.assertIn("Blocks changed to on", recent["message"])

    async def test_failed_action_names_are_reported_and_remembered(self):
        gateway = Gateway(failed=("light.blocks",))
        engine = WholeHomeSituationalIntelligence(
            Client(),
            self.assembler,
            self.timeline,
            gateway,
            SituationalIntelligencePolicy(maximum_entities=50),
        )
        result = await engine.handle(
            "Turn off all lights that are still on in the upstairs office",
            "one",
            source_id="panel",
        )
        self.assertIn("Unavailable: Blocks.", result["message"])
        followup = await engine.handle(
            "Which device was unavailable?", "two", source_id="panel"
        )
        self.assertEqual(followup["message"], "Unavailable: Blocks.")

    async def test_confirmation_keeps_exact_action_payload(self):
        gateway = Gateway("requires_confirmation")
        engine = WholeHomeSituationalIntelligence(
            Client(),
            self.assembler,
            self.timeline,
            gateway,
            SituationalIntelligencePolicy(maximum_entities=50),
        )
        result = await engine.handle(
            "Turn off all lights in the upstairs office", "one"
        )
        self.assertEqual(result["status"], "requires_confirmation")
        self.assertEqual(
            result["action_payload"]["entity_ids"],
            ("light.blocks", "light.office"),
        )

    async def test_unrelated_conversation_is_not_intercepted(self):
        result = await self.engine.handle("Who are you?", "one")
        self.assertIsNone(result)
        unresolved = await self.engine.handle(
            "What is the status of the porch lights?", "one"
        )
        self.assertIsNone(unresolved)

    def test_floor_references_extend_existing_deterministic_resolver(self):
        resolver = EntityReferenceResolver(
            {"light.blocks", "light.office"},
            floors={"upstairs": ("light.blocks", "light.office")},
        )
        self.assertEqual(
            resolver.resolve("upstairs", "light"),
            ("light.blocks", "light.office"),
        )
        self.assertTrue(resolver.is_collective("upstairs"))

    def test_timeline_can_adopt_existing_permitted_read_authorization(self):
        policy = EventTimelinePolicy(True, ("state_changed",), ())
        self.assertFalse(policy.permits("state_changed", "light.blocks"))
        policy.authorize_permitted_entities(("light.blocks",))
        self.assertTrue(policy.permits("state_changed", "light.blocks"))
        self.assertFalse(policy.permits("state_changed", "light.private"))
