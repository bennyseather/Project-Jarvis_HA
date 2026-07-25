import tempfile
import unittest
from pathlib import Path
import yaml

from jarvis.homeassistant.enrollment import HomeAccessEnrollment
from jarvis.models.home_assistant_gateway import HomeAssistantCapabilityCatalog, HomeAssistantServiceDefinition


class HomeAccessEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "general.yaml"
        self.path.write_text("home_assistant:\n  action_policy: {}\n", encoding="utf-8")
        catalog = HomeAssistantCapabilityCatalog(
            (HomeAssistantServiceDefinition("light", "turn_on"), HomeAssistantServiceDefinition("cover", "close_cover")),
            frozenset({"light.blocks", "cover.living_room"}),
        )
        self.enrollment = HomeAccessEnrollment(self.path, catalog)

    def tearDown(self): self.temp.cleanup()

    def test_explicit_read_action_and_alias_enrollment(self):
        self.assertEqual(self.enrollment.enroll_read("light.blocks")["status"], "success")
        self.assertEqual(self.enrollment.enroll_action("light.blocks", "light.turn_on")["status"], "success")
        self.assertEqual(self.enrollment.set_alias("blocks", "light.blocks")["status"], "success")
        config = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.assertEqual(config["home_assistant"]["allowed_read_entities"], ["light.blocks"])
        self.assertEqual(config["home_assistant"]["entity_aliases"], {"blocks":"light.blocks"})

    def test_high_impact_domains_cannot_use_normal_risk(self):
        self.assertEqual(self.enrollment.enroll_action("cover.living_room", "cover.close_cover")["message"], "high_impact_classification_required")
        self.assertEqual(self.enrollment.enroll_action("cover.living_room", "cover.close_cover", "high")["status"], "success")

    def test_discovery_is_not_enrollment(self):
        self.assertIn("cover.living_room", self.enrollment.discover("cover")["entities"])
        self.assertEqual(yaml.safe_load(self.path.read_text(encoding="utf-8"))["home_assistant"]["action_policy"], {})
