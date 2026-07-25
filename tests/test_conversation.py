import unittest

from jarvis.core.conversation import Conversation


class ConversationTests(unittest.TestCase):
    def test_history_is_bounded_and_in_process(self):
        conversation = Conversation(max_messages=2)
        conversation.add_user_message("one")
        conversation.add_assistant_message("two")
        conversation.add_user_message("three")
        self.assertEqual(
            [(message.role, message.content) for message in conversation.history()],
            [("assistant", "two"), ("user", "three")],
        )

    def test_too_small_history_is_rejected(self):
        with self.assertRaises(ValueError):
            Conversation(max_messages=1)
