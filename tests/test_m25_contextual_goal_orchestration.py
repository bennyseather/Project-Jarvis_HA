import unittest

from jarvis.homeassistant.compound_orchestration import (
    CompoundHomeOrchestrator,
    CompoundOrchestrationPolicy,
)
from jarvis.homeassistant.contextual_goals import ContextualGoalManager
from jarvis.homeassistant.home_topology import HomeTopologyAssembler
from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore


STATES = [
    {"entity_id": "light.lounge", "state": "on", "attributes": {"friendly_name": "Lounge Light"}},
    {"entity_id": "cover.lounge", "state": "open", "attributes": {"friendly_name": "Lounge Blinds"}},
    {"entity_id": "scene.movie", "state": "scening", "attributes": {"friendly_name": "Movie Mode"}},
]


class Client:
    async def get_states(self):
        return STATES


class Gateway:
    def __init__(self):
        self.executed = []

    def request(self, proposal):
        return {"status": "immediate_action", "summary": proposal.summary}

    async def execute_immediate(self, proposal):
        self.executed.append(proposal)
        return {"status": "success", "succeeded": proposal.entity_ids, "failed": ()}


class M25ContextualGoalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = InMemoryKnowledgeStore()
        self.gateway = Gateway()
        assembler = HomeTopologyAssembler(
            [{"area_id": "lounge", "name": "Lounge"}],
            [],
            [
                {"ei": "light.lounge", "ai": "lounge"},
                {"ei": "cover.lounge", "ai": "lounge"},
                {"ei": "scene.movie", "ai": "lounge"},
            ],
            [],
            {item["entity_id"] for item in STATES},
            {item["entity_id"] for item in STATES},
            maximum_entities=20,
        )
        compound = CompoundHomeOrchestrator(
            Client(), assembler, self.gateway, CompoundOrchestrationPolicy()
        )
        self.goals = ContextualGoalManager(self.store, compound)

    async def test_goal_vocabulary_is_explicit_inspectable_correctable_and_deletable(self):
        taught = self.goals.manage(
            "teach goal movie night | turn off the lounge light and close the lounge blinds"
        )
        self.assertEqual(taught["status"], "success")
        self.assertIn("movie night", self.goals.manage("show goals")["message"])
        self.assertIn(
            "turn off",
            self.goals.manage("explain goal movie night")["message"],
        )
        corrected = self.goals.manage(
            "correct goal movie night | turn on movie mode"
        )
        self.assertEqual(corrected["status"], "success")
        result = await self.goals.handle("Prepare for movie night", "one")
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.gateway.executed[-1].domain, "scene")
        deleted = self.goals.manage("forget goal movie night")
        self.assertEqual(deleted["status"], "success")
        self.assertIsNone(await self.goals.handle("movie night", "one"))

    def test_natural_delete_forms_and_singular_show_are_goal_scoped(self):
        self.goals.manage(
            "teach goal start work | turn on movie mode", "one"
        )
        shown = self.goals.manage("show goal", "one")
        self.assertIn("start work", shown["message"])
        deleted = self.goals.manage("delete this goal", "one")
        self.assertEqual(deleted["status"], "success")
        self.assertEqual(self.goals.goals(), ())

        self.goals.manage(
            "teach goal start work | turn on movie mode", "one"
        )
        deleted = self.goals.manage("delete start work", "one")
        self.assertEqual(deleted["status"], "success")
        self.assertEqual(self.goals.goals(), ())

    async def test_current_state_removes_unnecessary_actions(self):
        self.goals.manage(
            "teach goal guest ready | turn on the lounge light and close the lounge blinds"
        )
        result = await self.goals.handle("Get the lounge guest ready", "one")
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(self.gateway.executed), 1)
        self.assertEqual(self.gateway.executed[0].domain, "cover")
        self.assertIn(
            "explicit user-provided",
            result["goal_context"]["evidence"][0],
        )

    async def test_already_satisfied_goal_is_a_noop(self):
        self.goals.manage(
            "teach goal lights ready | turn on the lounge light"
        )
        result = await self.goals.handle("Make the lights ready", "one")
        self.assertEqual(result["status"], "success")
        self.assertIn("already satisfied", result["message"])
        self.assertEqual(self.gateway.executed, [])

    async def test_security_goal_forces_one_confirmation(self):
        self.goals.manage(
            "teach goal secure lounge | close the lounge blinds"
        )
        pending = await self.goals.handle("Secure lounge", "secure")
        self.assertEqual(pending["status"], "requires_confirmation")
        self.assertEqual(pending["risk"], "goal_confirmation_required")
        self.assertEqual(self.gateway.executed, [])
        confirmed = await self.goals._compound.confirm(
            pending["token"], pending["action_payload"]
        )
        self.assertEqual(confirmed["status"], "success")
        self.assertEqual(len(self.gateway.executed), 1)

    async def test_ambiguous_goal_names_require_clarification(self):
        self.goals.manage("teach goal movie time | turn on movie mode")
        self.goals.manage("teach goal guest prep | close the lounge blinds")
        result = await self.goals.handle(
            "Please do movie time and guest prep", "one"
        )
        self.assertEqual(result["status"], "clarification_required")
        self.assertEqual(self.gateway.executed, [])

    def test_runtime_and_addon_package_include_m25(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        application = (root / "src/jarvis/core/application.py").read_text()
        self.assertIn("contextual_goals.handle", application)
        addon = root / "home_assistant/addons/jarvis/app/src/jarvis"
        self.assertTrue((addon / "homeassistant/contextual_goals.py").exists())
        self.assertTrue((addon / "models/contextual_goal.py").exists())


if __name__ == "__main__":
    unittest.main()
