"""Device identity is not proof of an out-of-band answer consumer."""
import asyncio
from types import SimpleNamespace
import unittest

from jarvis.homeassistant.conversation_bridge import JarvisConversationBridge
from jarvis.responsive_orchestration import ResponsiveVoiceCoordinator


class CompanionTextReplyTests(unittest.IsolatedAsyncioTestCase):
    def setup_bridge(self):
        self.events = []
        self.routes = []
        self.requests = []
        async def event(name, data):
            self.events.append((name, data))
        coordinator = ResponsiveVoiceCoordinator(client=SimpleNamespace(dispatch_event=event))
        async def handle(text, conversation_id, **kwargs):
            self.requests.append((conversation_id, kwargs))
            await asyncio.sleep(0.01)
            return {'status': 'success', 'message': 'The final, verified answer.'}
        app = SimpleNamespace(container=SimpleNamespace(responsive_voice=coordinator,
            proactive_delivery=SimpleNamespace(set_voice_route=self.routes.append)),
            handle_request=handle, _user_message=lambda result: result['message'])
        return JarvisConversationBridge(app), coordinator

    async def test_companion_device_event_route_returns_final_reply(self):
        for identifier in ('01JCOMPANION', None, 'random:phone:conversation'):
            bridge, coordinator = self.setup_bridge()
            out = await bridge.process('Explain our plans tomorrow', conversation_id=identifier,
                voice_mode=True, source_id='mobile-device', proactive_voice_route={
                    'event_type': 'jarvis_voice_follow_up', 'source_id': 'mobile-device', 'target_id': 'mobile-device'})
            self.assertEqual(out, {'status': 'success', 'message': 'The final, verified answer.'})
            self.assertEqual(self.events, [])
            self.assertEqual(self.routes, [None])
            self.assertEqual(coordinator._jobs, {})
            self.assertEqual(self.requests[0][1]['source_id'], 'mobile-device')

    async def test_missing_mismatched_or_unsafe_browser_target_waits_for_answer(self):
        for identifier, target in (('jarvis-voice:desk:session', 'other'),
                                   ('jarvis-voice::session', ''),
                                   ('jarvis-voice:desk%2Fother:session', 'desk/other'),
                                   ('jarvis-voice:desk', 'desk')):
            bridge, coordinator = self.setup_bridge()
            out = await bridge.process('Explain our plans', conversation_id=identifier, voice_mode=True,
                proactive_voice_route={'event_type': 'jarvis_voice_follow_up', 'target_id': target})
            self.assertEqual(out['status'], 'success')
            self.assertEqual(self.events, [])
            self.assertEqual(coordinator._jobs, {})

    async def test_explicit_browser_retains_scoped_followup_delivery(self):
        for identifier in ('jarvis-voice:desk:session', 'jarvis-voice:%64esk:session'):
            bridge, coordinator = self.setup_bridge()
            out = await bridge.process('Explain our plans', conversation_id=identifier, voice_mode=True,
                proactive_voice_route={'event_type': 'jarvis_voice_follow_up', 'target_id': 'desk'})
            self.assertEqual(out['status'], 'in_progress')
            await asyncio.sleep(0.05)
            self.assertEqual(len(self.events), 1)
            self.assertEqual(self.events[0][1]['target_id'], 'desk')
            self.assertEqual(self.events[0][1]['message'], 'The final, verified answer.')

    async def test_ordinary_text_without_device_route_stays_synchronous(self):
        bridge, coordinator = self.setup_bridge()
        out = await bridge.process('Explain our plans', conversation_id='text', voice_mode=False)
        self.assertEqual(out['status'], 'success')
        self.assertEqual(self.events, [])
        self.assertEqual(coordinator._jobs, {})

    async def test_explicit_external_tts_route_is_unchanged(self):
        bridge, coordinator = self.setup_bridge()
        observed = []
        async def capture(operation, **kwargs):
            observed.append(kwargs['route'])
            return await operation
        coordinator.execute = capture
        route = {'tts_entity_id': 'tts.fixture', 'media_player_entity_id': 'media_player.fixture'}
        out = await bridge.process('Explain our plans', conversation_id='external', voice_mode=True,
                                   proactive_voice_route=route)
        self.assertEqual(out['status'], 'success')
        self.assertEqual(observed, [route])


if __name__ == '__main__':
    unittest.main()
