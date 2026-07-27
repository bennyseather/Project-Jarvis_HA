import importlib.util
import sys
import types
import unittest
from pathlib import Path


def load_voice_module():
    root = Path(__file__).parents[1]
    package_name = "jarvis_component_test"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package
    for module_name in ("const", "voice"):
        path = (
            root
            / "home_assistant"
            / "custom_components"
            / "jarvis_conversation"
            / f"{module_name}.py"
        )
        spec = importlib.util.spec_from_file_location(
            f"{package_name}.{module_name}", path
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return sys.modules[f"{package_name}.voice"]


voice = load_voice_module()


class M20VoiceTests(unittest.TestCase):
    def setUp(self):
        self.options = {
            "external_voice_output": True,
            "input_device_id": "device-panel",
            "output_media_player_entity_id": "media_player.loftstue_group",
            "tts_entity_id": "tts.home_assistant_cloud",
            "tts_language": "en-GB",
            "tts_voice": "OriginalBritishVoice",
            "suppress_local_audio": True,
        }

    def test_external_routing_requires_exact_configured_input_device(self):
        self.assertTrue(
            voice.should_route_external(self.options, "device-panel")
        )
        self.assertFalse(
            voice.should_route_external(self.options, "another-device")
        )
        self.assertFalse(voice.should_route_external(self.options, None))
        self.options["external_voice_output"] = False
        self.assertFalse(
            voice.should_route_external(self.options, "device-panel")
        )

    def test_tts_payload_targets_selected_provider_and_speaker(self):
        payload = voice.build_tts_service_data(
            self.options, "Blocks is 21.0 percent; ready."
        )
        self.assertEqual(payload["entity_id"], "tts.home_assistant_cloud")
        self.assertEqual(
            payload["media_player_entity_id"],
            "media_player.loftstue_group",
        )
        self.assertEqual(payload["language"], "en-GB")
        self.assertEqual(
            payload["options"], {"voice": "OriginalBritishVoice"}
        )
        self.assertEqual(payload["message"], "Blocks is 21 percent, ready.")

    def test_spoken_formatter_removes_common_entity_identifiers_and_bounds_text(self):
        self.assertEqual(
            voice.format_spoken_response("light.upstairs_office is on."),
            "upstairs office is on.",
        )
        bounded = voice.format_spoken_response("word " * 300, 80)
        self.assertLessEqual(len(bounded), 81)
        self.assertTrue(bounded.endswith("."))
