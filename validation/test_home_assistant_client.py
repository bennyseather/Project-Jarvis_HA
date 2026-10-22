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


class _ResponseSocket(_FreshSocket):
    async def recv(self):
        return json.dumps({
            "type": "result",
            "success": True,
            "result": {"response": {
                "calendar.jarvis_travels": {"events": [{"summary": "Flight"}]}
            }},
        })


class HomeAssistantClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_today_read_isolated_and_closed(self):
        client=HomeAssistantClient('http://supervisor/core','token',_Logger())
        primary=_BrokenSocket();client.websocket=primary
        fresh=_FreshSocket();fresh.closed=False
        async def recv():return json.dumps({'id':1,'type':'result','success':True,'result':{'read_only':True}})
        async def close():fresh.closed=True
        fresh.recv=recv;fresh.close=close
        async def connect(reader):reader.websocket=fresh
        with patch.object(HomeAssistantClient,'_connect_socket',connect):
            self.assertTrue((await client.get_household_today())['read_only'])
        self.assertIs(client.websocket,primary);self.assertTrue(fresh.closed)
        self.assertEqual(fresh.request,{'id':1,'type':'jarvis_conversation/household'})
    async def test_today_rejects_failed_or_wrong_response(self):
        for response in ({'id':1,'type':'result','success':False},{'id':2,'type':'result','success':True}):
            fresh=_FreshSocket()
            async def recv():return json.dumps(response)
            fresh.recv=recv
            async def connect(reader):reader.websocket=fresh
            with patch.object(HomeAssistantClient,'_connect_socket',connect):
                with self.assertRaises(RuntimeError):
                    await HomeAssistantClient('http://supervisor/core','token',_Logger()).get_household_today()
    async def test_future_period_forwarded_on_read_only_command(self):
        fresh=_FreshSocket()
        async def recv():return json.dumps({'id':1,'type':'result','success':True,'result':{}})
        fresh.recv=recv
        async def connect(reader):reader.websocket=fresh
        with patch.object(HomeAssistantClient,'_connect_socket',connect):
            await HomeAssistantClient('http://supervisor/core','token',_Logger()).get_household_today('tomorrow')
        self.assertEqual(fresh.request,{'id':1,'type':'jarvis_conversation/household','period':'tomorrow'})
    async def test_invalid_period_rejected_before_connect(self):
        with self.assertRaises(ValueError):
            await HomeAssistantClient('http://invalid','token',_Logger()).get_household_today('arbitrary')
    async def test_custom_dates_forwarded_and_bounded(self):
        from datetime import datetime,timedelta
        from zoneinfo import ZoneInfo
        today=datetime.now(ZoneInfo('Europe/Oslo')).date()
        fresh=_FreshSocket()
        async def recv():return json.dumps({'id':1,'type':'result','success':True,'result':{}})
        fresh.recv=recv
        async def connect(reader):reader.websocket=fresh
        client=HomeAssistantClient('http://supervisor/core','token',_Logger())
        with patch.object(HomeAssistantClient,'_connect_socket',connect):
            await client.get_household_today('custom',start_date=today.isoformat(),end_date=(today+timedelta(days=2)).isoformat())
        self.assertEqual(fresh.request['start_date'],today.isoformat())
        self.assertEqual(fresh.request['type'],'jarvis_conversation/household')
        for period,offset in [('today',1),('custom',15),('custom',0)]:
            with self.assertRaises(ValueError):
                await client.get_household_today(period,start_date=today.isoformat(),end_date=(today+timedelta(days=offset)).isoformat())
    async def test_response_service_uses_an_isolated_socket(self):
        logger = _Logger()
        client = HomeAssistantClient("http://supervisor/core", "token", logger)
        primary = _BrokenSocket()
        client.websocket = primary
        fresh = _ResponseSocket()

        async def connect(reader):
            reader.websocket = fresh

        with patch.object(HomeAssistantClient, "_connect_socket", connect):
            response = await client.call_service_response(
                "calendar", "get_events", {"entity_id": "calendar.jarvis_travels"}
            )

        self.assertEqual(response["calendar.jarvis_travels"]["events"][0]["summary"], "Flight")
        self.assertEqual(fresh.request["type"], "call_service")
        self.assertTrue(fresh.request["return_response"])
        self.assertIs(client.websocket, primary)

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

    async def test_follow_up_event_uses_an_isolated_socket(self):
        logger = _Logger()
        client = HomeAssistantClient("http://supervisor/core", "token", logger)
        class EventResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_args): pass

        with patch("jarvis.homeassistant.client.urlopen", return_value=EventResponse()) as call:
            self.assertTrue(await client.dispatch_event(
                "jarvis_voice_follow_up", {"message": "Ready.", "source_id": "desk"}
            ))
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, "http://supervisor/core/api/events/jarvis_voice_follow_up")
        self.assertEqual(json.loads(request.data), {"message": "Ready.", "source_id": "desk"})


if __name__ == "__main__":
    unittest.main()
