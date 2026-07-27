import json
import unittest

from jarvis.homeassistant.client import HomeAssistantClient


class _Logger:
    def __init__(self):
        self.warnings = []

    def info(self, _message):
        pass

    def warning(self, message):
        self.warnings.append(message)


class _BrokenSocket:
    async def send(self, _message):
        raise RuntimeError("connection closed")


class _FreshSocket:
    async def send(self, message):
        self.request = json.loads(message)

    async def recv(self):
        return json.dumps(
            {
                "type": "result",
                "success": True,
                "result": [
                    {
                        "entity_id": "light.blocks",
                        "state": "on",
                        "attributes": {},
                    }
                ],
            }
        )


class HomeAssistantClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_state_read_reconnects_once_after_stale_socket(self):
        logger = _Logger()
        client = HomeAssistantClient("http://supervisor/core", "token", logger)
        client.websocket = _BrokenSocket()
        fresh = _FreshSocket()
        reconnects = 0

        async def reconnect():
            nonlocal reconnects
            reconnects += 1
            client.websocket = fresh

        client._connect_socket = reconnect
        states = await client.get_states()

        self.assertEqual(reconnects, 1)
        self.assertEqual(states[0]["entity_id"], "light.blocks")
        self.assertEqual(fresh.request["type"], "get_states")
        self.assertEqual(len(logger.warnings), 1)


if __name__ == "__main__":
    unittest.main()
