import unittest

from jarvis.homeassistant.conversation_bridge import JarvisConversationBridge


class Assistant:
    async def confirm_action(self, token, payload): return {"status":"success"}


class Container:
    read_only_assistant = Assistant()


class App:
    def __init__(self): self.container = Container(); self._pending_action_payloads = {}
    async def handle_request(self, text): return {"status":"requires_confirmation","token":"once","summary":"Turn on blocks","action_payload":{"domain":"light"}}
    @staticmethod
    def _user_message(result): return result.get("message", "Action completed.")


class ConversationBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmation_stays_in_existing_lifecycle(self):
        bridge = JarvisConversationBridge(App())
        pending = await bridge.process("turn on blocks")
        self.assertEqual(pending["status"], "requires_confirmation")
        self.assertEqual((await bridge.process("", pending["confirmation_token"]))["status"], "success")
        self.assertEqual((await bridge.process("", pending["confirmation_token"]))["status"], "forbidden")
