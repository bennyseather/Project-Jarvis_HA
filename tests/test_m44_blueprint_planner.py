import tempfile
import unittest
from pathlib import Path

from jarvis.homeassistant.blueprint_planner import BlueprintPlanner


DETAILS = '''Name: Office Work Greeting
Trigger: Lumi Remote Switch - Short press
Actions: If time between 06:00 and 10:00 turn on office lights and greet me.
Include the weather and Reach Work calendar appointments through TTS.
If time between 15:00 and 18:00 turn them off. Otherwise toggle them.'''


class BlueprintPlannerTests(unittest.TestCase):
    def test_short_request_collects_details_instead_of_reading_entities(self):
        planner = BlueprintPlanner()
        result = planner.handle("create a blueprint for me", "c1")
        self.assertEqual(result["status"], "clarification_required")
        result = planner.handle(DETAILS, "c1")
        self.assertEqual(result["status"], "requires_confirmation")
        self.assertEqual(result["action_payload"]["kind"], "blueprint_install")

    def test_generated_blueprint_has_ui_selectors_and_dynamic_data_actions(self):
        planner = BlueprintPlanner()
        result = planner.handle("Create a blueprint. " + DETAILS, "c1")
        pending = planner._pending[result["token"]][3]
        for value in (
            "selector:\n        trigger:", "weather.get_forecasts",
            "calendar.get_events", "tts.speak", "homeassistant.toggle",
            "Lofstue Group Speaker", "Good morning, Benny",
        ):
            self.assertIn(value, pending)
        self.assertIn("{{ today_at('00:00') }}", pending)
        self.assertIn("{{ briefing }}", pending)
        self.assertNotIn('start_date_time: "{ today_at', pending)
        self.assertEqual(pending.count("continue_on_error: true"), 3)

    def test_name_stops_before_inline_trigger_field(self):
        planner = BlueprintPlanner()
        result = planner.handle(
            "Create a blueprint. Name: Office Work Greeting Trigger: Lumi Remote. "
            "Actions: include office weather and calendar briefing.",
            "c1",
        )
        self.assertIn("Office Work Greeting", result["summary"])
        self.assertNotIn("Trigger:", result["summary"])

    def test_install_is_confirmation_bound_and_path_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            planner = BlueprintPlanner(directory)
            result = planner.handle("Create a blueprint. " + DETAILS, "c1")
            denied = planner.confirm(result["token"], {"kind": "blueprint_install", "conversation_id": "other"})
            self.assertEqual(denied["status"], "forbidden")
            result = planner.handle("Create a blueprint. " + DETAILS, "c1")
            installed = planner.confirm(result["token"], result["action_payload"])
            path = Path(installed["path"])
            self.assertTrue(path.is_file())
            self.assertTrue(path.is_relative_to(Path(directory)))

    def test_unrelated_blueprint_uses_safe_generic_editor_inputs(self):
        planner = BlueprintPlanner()
        result = planner.handle(
            "Create a blueprint named Door Notice. Trigger when a door opens. Action send a notification.",
            "c1",
        )
        draft = planner._pending[result["token"]][3]
        self.assertIn("automation_actions", draft)
        self.assertNotIn("calendar.get_events", draft)
