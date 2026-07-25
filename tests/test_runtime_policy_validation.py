import unittest
from jarvis.core.application import JarvisApplication
class Tests(unittest.TestCase):
 def test_accepts_empty_safe_defaults(self):
  JarvisApplication._validate_home_assistant_policy({"allowed_read_entities":[],"action_policy":{"confirm_required":[],"high_impact":[],"allowed_entities":[]}})
 def test_rejects_malformed_authorization_values(self):
  with self.assertRaises(ValueError):JarvisApplication._validate_home_assistant_policy({"allowed_read_entities":"light.kitchen","action_policy":{}})
  with self.assertRaises(ValueError):JarvisApplication._validate_home_assistant_policy({"action_policy":{"allowed_entities":[""]}})
