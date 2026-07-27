import unittest

from jarvis.core.application import JarvisApplication


class RuntimePolicyValidationTests(unittest.TestCase):
    def test_accepts_empty_safe_defaults(self):
        JarvisApplication._validate_home_assistant_policy(
            {
                "allowed_read_entities": [],
                "action_policy": {
                    "confirm_required": [],
                    "high_impact": [],
                    "allowed_entities": [],
                },
            }
        )

    def test_rejects_malformed_authorization_values(self):
        with self.assertRaises(ValueError):
            JarvisApplication._validate_home_assistant_policy(
                {"allowed_read_entities": "light.kitchen", "action_policy": {}}
            )
        with self.assertRaises(ValueError):
            JarvisApplication._validate_home_assistant_policy(
                {"action_policy": {"allowed_entities": [""]}}
            )
        with self.assertRaises(ValueError):
            JarvisApplication._validate_home_assistant_policy(
                {"entity_aliases": {"": "light.blocks"}, "action_policy": {}}
            )

    def test_rejects_malformed_timeline_configuration(self):
        with self.assertRaises(ValueError):
            JarvisApplication._validate_timeline_config({"enabled": "yes"})
        with self.assertRaises(ValueError):
            JarvisApplication._validate_timeline_config({"allowed_entities": "light.blocks"})
        with self.assertRaises(ValueError):
            JarvisApplication._validate_timeline_config({"max_events": 0})

    def test_user_message_preserves_specific_clarification(self):
        message = JarvisApplication._user_message({
            "status": "clarification_required",
            "message": "That selection contains 116 permitted entities.",
        })
        self.assertEqual(message, "That selection contains 116 permitted entities.")
