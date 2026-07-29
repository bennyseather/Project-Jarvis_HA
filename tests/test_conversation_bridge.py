import unittest

from jarvis.homeassistant.conversation_bridge import JarvisConversationBridge


class Assistant:
    async def confirm_action(self, token, payload):
        return {"status": "success", "message": "Action completed."}


class Store:
    def __init__(self):
        self.messages = []

    @staticmethod
    def normalize_conversation_id(value):
        return value or "local-default"

    def add_message(self, conversation_id, role, content):
        self.messages.append((conversation_id, role, content))


class NaturalMemory:
    def handle(self, text, conversation_id):
        if text == "confirm memory memory-token":
            return {"status": "success", "message": "I will remember that."}
        return None

    def cancel_confirmation(self, token):
        pass


class Container:
    def __init__(self):
        self.read_only_assistant = Assistant()
        self.conversation_store = Store()
        self.natural_memory_controller = NaturalMemory()


class App:
    def __init__(self):
        self.container = Container()
        self._pending_action_payloads = {}
        self.mode = "action"
        self.last_source_id = None

    async def handle_request(
        self, text, conversation_id=None, *, voice_mode=False, source_id=None
    ):
        self.last_source_id = source_id
        if self.mode == "memory":
            return {
                "status": "requires_confirmation",
                "confirmation_token": "memory-token",
                "message": "Sensitive memory requires confirmation.",
            }
        return {
            "status": "requires_confirmation",
            "token": f"once-{conversation_id or 'local-default'}",
            "summary": "Turn on blocks",
            "action_payload": {"domain": "light"},
        }

    @staticmethod
    def _user_message(result):
        return result.get("message", "Action completed.")


class ConversationBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_identity_reaches_the_application(self):
        app = App()
        bridge = JarvisConversationBridge(app)
        await bridge.process(
            "turn on blocks",
            conversation_id="one",
            source_id="panel",
        )
        self.assertEqual(app.last_source_id, "panel")

    async def test_confirmation_stays_in_existing_lifecycle(self):
        bridge = JarvisConversationBridge(App())
        pending = await bridge.process("turn on blocks", conversation_id="one")
        self.assertEqual(pending["status"], "requires_confirmation")
        self.assertEqual(
            pending["message"],
            "Confirm action: Turn on blocks. Reply: confirm once-one",
        )
        confirmed = await bridge.process(
            "confirm " + pending["confirmation_token"],
            conversation_id="one",
        )
        self.assertEqual(confirmed["status"], "success")
        reused = await bridge.process(
            "", pending["confirmation_token"], conversation_id="one"
        )
        self.assertEqual(reused["status"], "forbidden")

    async def test_voice_yes_is_bound_to_originating_conversation(self):
        bridge = JarvisConversationBridge(App())
        pending = await bridge.process(
            "turn on blocks", conversation_id="one", voice_mode=True
        )
        self.assertEqual(pending["message"], "Turn on blocks. Shall I proceed?")
        wrong = await bridge.process(
            "", pending["confirmation_token"], conversation_id="two"
        )
        self.assertEqual(wrong["status"], "forbidden")
        self.assertEqual(
            (await bridge.process("yes", conversation_id="one"))["status"],
            "success",
        )

    async def test_voice_no_cancels_without_executing(self):
        app = App()
        bridge = JarvisConversationBridge(app)
        await bridge.process("turn on blocks", conversation_id="one", voice_mode=True)
        cancelled = await bridge.process("no", conversation_id="one", voice_mode=True)
        self.assertEqual(cancelled["message"], "Cancelled. I will not proceed.")
        self.assertNotIn("once-one", app._pending_action_payloads)

    async def test_sensitive_memory_accepts_natural_yes(self):
        app = App()
        app.mode = "memory"
        bridge = JarvisConversationBridge(app)
        pending = await bridge.process(
            "remember my medical detail",
            conversation_id="one",
            voice_mode=True,
        )
        self.assertIn("private", pending["message"])
        result = await bridge.process("yes please", conversation_id="one")
        self.assertEqual(result["status"], "success")
