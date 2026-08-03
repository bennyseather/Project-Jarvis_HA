import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.models.event_timeline import TimelineEvent
from jarvis.models.proactive import (
    ProactiveCandidate,
    ProactiveSuggestionKind,
    ProactiveSuggestionStatus,
)
from jarvis.models.reflection import ReflectionKind, ReflectionRecord
from jarvis.proactive.controller import NaturalProactiveController
from jarvis.proactive.delivery import HomeAssistantProactiveDelivery
from jarvis.proactive.detector import ProactiveOpportunityDetector
from jarvis.proactive.manager import ProactiveAssistanceManager
from jarvis.proactive.policy import ProactiveAssistancePolicy
from jarvis.proactive.store import SQLiteProactiveStore


class Clock:
    def __init__(self):
        self.now = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class StaticDetector:
    def __init__(self, *candidates):
        self.candidates = candidates

    def detect(self, **_kwargs):
        return self.candidates


class ActionGateway:
    def __init__(self):
        self.executed = []

    def request(self, proposal):
        self.requested = proposal
        return {"status": "immediate_action", "summary": proposal.summary}

    async def execute_immediate(self, proposal):
        self.executed.append(proposal)
        return {"status": "success", "message": "Action completed."}


class ConfirmationGateway(ActionGateway):
    def request(self, proposal):
        self.requested = proposal
        return {
            "status": "requires_confirmation",
            "token": "confirm-one",
            "summary": proposal.summary,
        }


class Client:
    def __init__(self):
        self.calls = []

    async def call_service(self, domain, service, data):
        self.calls.append((domain, service, data))
        return True


class M22ProactiveAssistanceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "jarvis.sqlite3"
        self.clock = Clock()
        self.store = SQLiteProactiveStore(self.path)

    def test_home_assistant_os_exposes_explicit_proactive_voice_opt_in(self):
        addon = Path("home_assistant/addons/jarvis/config.yaml").read_text(
            encoding="utf-8"
        )
        entrypoint = Path(
            "home_assistant/addons/jarvis/addon_entrypoint.py"
        ).read_text(encoding="utf-8")
        manifest = Path(
            "home_assistant/custom_components/jarvis_conversation/manifest.json"
        ).read_text(encoding="utf-8")
        self.assertIn("proactive_voice_enabled: false", addon)
        self.assertIn("proactive_voice_enabled: bool", addon)
        self.assertIn('options.get("proactive_voice_enabled", False)', entrypoint)
        self.assertIn('"version": "0.22.1"', manifest)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_policy_validates_bounds_quiet_hours_and_sensitive_exclusion(self):
        policy = ProactiveAssistancePolicy.from_config({
            "minimum_confidence": 0.9,
            "quiet_start": "22:00",
            "quiet_end": "07:00",
            "voice_enabled": False,
        })
        self.assertTrue(policy.is_quiet(
            datetime(2026, 7, 28, 23, 0, tzinfo=timezone.utc)
        ))
        self.assertFalse(policy.is_quiet(self.clock()))
        sensitive = ProactiveCandidate(
            ProactiveSuggestionKind.FOLLOW_UP,
            "private",
            "Private suggestion",
            "Sensitive source",
            1.0,
            sensitive=True,
        )
        self.assertFalse(policy.permits_candidate(sensitive, suppressed=False))
        with self.assertRaises(ValueError):
            ProactiveAssistancePolicy.from_config({"maximum_pending": 0})
        with self.assertRaises(ValueError):
            ProactiveAssistancePolicy.from_config({"quiet_start": "night"})
        with self.assertRaises(ValueError):
            ProactiveAssistancePolicy.from_config({"voice_enabled": "yes"})

    def test_detector_is_bounded_explainable_and_does_not_persist_raw_inputs(self):
        detector = ProactiveOpportunityDetector(
            low_battery_threshold=20, routine_repeat_threshold=3
        )
        reflection = ReflectionRecord(
            "follow-one",
            ReflectionKind.FOLLOW_UP,
            "office",
            "Ask whether the office preference is still current.",
            0.9,
            ("memory-one",),
            ("conversation-one",),
            False,
            self.clock(),
            self.clock(),
        )
        events = tuple(
            TimelineEvent(index, "state_changed", "light.blocks", self.clock(), "on")
            for index in range(1, 4)
        )
        candidates = detector.detect(
            states=({
                "entity_id": "sensor.remote_battery",
                "state": "12",
                "attributes": {
                    "device_class": "battery",
                    "friendly_name": "Remote Battery",
                },
            },),
            timeline_events=events,
            reflections=(reflection,),
        )
        self.assertEqual(
            {item.kind for item in candidates},
            {
                ProactiveSuggestionKind.ATTENTION,
                ProactiveSuggestionKind.FOLLOW_UP,
                ProactiveSuggestionKind.ROUTINE,
            },
        )
        self.assertTrue(all(item.reason for item in candidates))
        self.assertEqual(self.store.list_records(), ())

    def test_schema_four_records_survive_restart_and_hard_delete(self):
        manager = self._manager(self._candidate())
        suggestion = manager.refresh()[0]
        self.store.close()
        self.store = SQLiteProactiveStore(self.path)
        self.assertIsNotNone(self.store.get(suggestion.suggestion_id))
        connection = sqlite3.connect(self.path)
        self.assertEqual(
            connection.execute("SELECT version FROM schema_version").fetchone()[0],
            4,
        )
        connection.close()
        self.store.delete(suggestion.suggestion_id)
        self.assertEqual(self.store.list_records(), ())

    async def test_natural_controls_explain_snooze_suppress_and_clear(self):
        manager = self._manager(self._candidate())
        manager.refresh()
        controller = NaturalProactiveController(manager)
        listed = await controller.handle("What needs my attention?", "one")
        self.assertIn("1 suggestions", listed["message"])
        explained = await controller.handle("Why are you suggesting that?", "one")
        self.assertIn("because", explained["message"])
        snoozed = await controller.handle("Not now", "one")
        self.assertEqual(snoozed["status"], "success")
        self.clock.now += timedelta(minutes=121)
        manager.refresh()
        await controller.handle("What needs my attention?", "one")
        suppressed = await controller.handle("Never suggest this again", "one")
        self.assertIn("not suggest", suppressed["message"])
        manager.refresh()
        self.assertEqual(manager.pending(), ())
        shown = await controller.handle("Show suppressed suggestions", "one")
        self.assertIn("attention:test", shown["message"])
        cleared = await controller.handle("Clear suggestion suppressions", "one")
        self.assertIn("Removed 1", cleared["message"])

    async def test_accepted_action_uses_existing_gateway_only(self):
        gateway = ActionGateway()
        candidate = ProactiveCandidate(
            ProactiveSuggestionKind.ATTENTION,
            "action:test",
            "Blocks can be turned off.",
            "The user explicitly selected this suggestion.",
            1.0,
            action={
                "domain": "light",
                "service": "turn_off",
                "entity_ids": ("light.blocks",),
                "service_data": {},
                "summary": "Turn off Blocks",
            },
        )
        manager = self._manager(candidate, gateway=gateway)
        manager.refresh()
        manager.attention("one")
        result = await manager.accept_current("one")
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(gateway.executed), 1)
        stored = self.store.list_records()[0]
        self.assertIs(stored.status, ProactiveSuggestionStatus.ACCEPTED)

    async def test_action_confirmation_uses_existing_confirmation_lifecycle(self):
        gateway = ConfirmationGateway()
        candidate = replace(
            self._candidate(),
            action={
                "domain": "light",
                "service": "turn_off",
                "entity_ids": ("light.blocks",),
                "service_data": {},
                "summary": "Turn off Blocks",
            },
        )
        manager = self._manager(candidate, gateway=gateway)
        manager.refresh()
        manager.attention("one")
        result = await manager.accept_current("one")
        self.assertEqual(result["status"], "requires_confirmation")
        self.assertEqual(result["token"], "confirm-one")
        self.assertEqual(result["action_payload"]["entity_ids"], ["light.blocks"])
        self.assertEqual(gateway.executed, [])

    async def test_informational_acceptance_never_executes_and_delivery_deduplicates(self):
        manager = self._manager(self._candidate())
        suggestion = manager.refresh()[0]
        manager.attention("one")
        result = await manager.accept_current("one")
        self.assertIn("No Home Assistant changes", result["message"])

        client = Client()
        delivery = HomeAssistantProactiveDelivery(
            manager, manager.policy, self.clock
        )
        await delivery.deliver(client)
        await delivery.deliver(client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][:2], ("persistent_notification", "create"))
        self.assertIn(
            "notification", self.store.get(suggestion.suggestion_id).delivered_channels
        )

    async def test_voice_requires_both_policy_opt_in_and_registered_m20_route(self):
        policy = ProactiveAssistancePolicy.from_config({
            "quiet_start": "23:00",
            "quiet_end": "06:00",
            "voice_enabled": True,
            "notification_enabled": False,
        })
        manager = ProactiveAssistanceManager(
            self.store, policy, StaticDetector(self._candidate()), clock=self.clock
        )
        manager.refresh()
        client = Client()
        delivery = HomeAssistantProactiveDelivery(manager, policy, self.clock)
        await delivery.deliver(client)
        self.assertEqual(client.calls, [])
        delivery.set_voice_route({
            "tts_entity_id": "tts.cloud",
            "media_player_entity_id": "media_player.loftstue_group",
            "language": "en-GB",
            "voice": "OriginalVoice",
        })
        await delivery.deliver(client)
        self.assertEqual(client.calls[0][:2], ("tts", "speak"))

    async def test_expiry_maximum_pending_and_quiet_hours_are_enforced(self):
        candidates = tuple(
            replace(self._candidate(), subject=f"attention:{index}")
            for index in range(12)
        )
        policy = ProactiveAssistancePolicy.from_config({
            "maximum_pending": 3,
            "expiry_hours": 1,
            "quiet_start": "00:00",
            "quiet_end": "23:59",
        })
        manager = ProactiveAssistanceManager(
            self.store, policy, StaticDetector(*candidates), clock=self.clock
        )
        self.assertEqual(len(manager.refresh()), 3)
        client = Client()
        await HomeAssistantProactiveDelivery(
            manager, policy, self.clock
        ).deliver(client)
        self.assertEqual(client.calls, [])
        manager._detector = StaticDetector()
        self.clock.now += timedelta(hours=2)
        manager.refresh()
        self.assertEqual(manager.pending(), ())

    def _manager(self, candidate, gateway=None):
        policy = ProactiveAssistancePolicy.from_config({
            "quiet_start": "23:00",
            "quiet_end": "06:00",
            "cooldown_minutes": 60,
        })
        return ProactiveAssistanceManager(
            self.store,
            policy,
            StaticDetector(candidate),
            gateway,
            self.clock,
        )

    @staticmethod
    def _candidate():
        return ProactiveCandidate(
            ProactiveSuggestionKind.ATTENTION,
            "attention:test",
            "A test item needs attention.",
            "A deterministic approved source produced it.",
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
