import json
import unittest
from unittest.mock import patch

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

    async def close(self):
        pass


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

    async def test_service_dispatch_uses_an_isolated_result_task(self):
        logger = _Logger()
        client = HomeAssistantClient("http://supervisor/core", "token", logger)
        fresh = _FreshSocket()

        async def connect(dispatcher):
            dispatcher.websocket = fresh

        with patch.object(HomeAssistantClient, "_connect_socket", connect):
            result_task = await client.dispatch_service(
                "light", "turn_on", {"entity_id": ["light.blocks"]}
            )
            self.assertTrue(await result_task)

        self.assertEqual(fresh.request["type"], "call_service")
        self.assertEqual(fresh.request["service"], "turn_on")


if __name__ == "__main__":
    unittest.main()
