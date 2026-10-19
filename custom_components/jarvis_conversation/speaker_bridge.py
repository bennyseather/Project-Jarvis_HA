"""Optional paired development microphone; no recordings or identity elevation."""
import asyncio
from dataclasses import dataclass
import hashlib
import http.client
import json
from pathlib import Path
import re
import ssl
import time
import voluptuous as vol
from homeassistant.components import websocket_api

from .speaker_context import SharedSpeakerTurns
from .speaker_capture import ActivatedCaptureTap
from .speaker_transport import CaptureCredential, PinnedCaptureSender

DIRECTORY = Path('/config/jarvis-speaker-capture')


@dataclass(frozen=True)
class SpeakerTurn:
    text: str
    conversation_id: str
    member_id: str | None = None

    def __iter__(self):
        # Preserve the pair-shaped Python interface; metadata is explicit.
        yield self.text
        yield self.conversation_id

    @property
    def reference(self):
        return {'member_id': self.member_id, 'basis': 'voice_match' if self.member_id else 'unknown',
                'conversation_id': self.conversation_id}


@dataclass
class _Paired:
    identifier: str
    source_id: str
    expires: float
    sender: object
    last_result: str = 'paired'
    tap: object = None


class SpeakerBridge:
    def __init__(self, config, *, clock=time.monotonic):
        if set(config) != {'enabled', 'api_key_hex', 'certificate_sha256'} or config['enabled'] is not True:
            raise ValueError('Reviewed speaker config required')
        if not re.fullmatch('[a-f0-9]{64}', config['api_key_hex']) or not re.fullmatch('[a-f0-9]{64}', config['certificate_sha256']):
            raise ValueError('Pinned speaker gateway required')
        self.key, self.pin, self.clock = config['api_key_hex'], config['certificate_sha256'], clock
        self.ssl = ssl.create_default_context(cafile=str(DIRECTORY/'ca.crt'))
        self.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
        self._pairs, self._runs = {}, {}
        self.turns = SharedSpeakerTurns(clock=clock)

    def _post(self, path, data, timeout):
        connection = http.client.HTTPSConnection('192.168.1.105', 10562, timeout=timeout, context=self.ssl)
        try:
            connection.connect()
            certificate = connection.sock.getpeercert(binary_form=True)
            if hashlib.sha256(certificate).hexdigest() != self.pin:
                raise PermissionError('Speaker certificate pin mismatch')
            connection.request('POST', path, body=json.dumps(data).encode(),
                headers={'Authorization': 'Bearer '+self.key, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            raw = response.read(8193)
            if response.status != 200 or len(raw) > 8192:
                raise PermissionError('Speaker gateway unavailable')
            return json.loads(raw)
        finally:
            connection.close()

    async def pair(self, connection, code):
        if type(code) is not str or not 20 <= len(code) <= 80:
            raise ValueError('Invalid microphone code')
        data = await asyncio.wait_for(asyncio.to_thread(self._post, '/pair', {'code': code}, 2), 2.5)
        fields = {'grant_id', 'key_id', 'source_id', 'secret_hex', 'expires_in'}
        if not isinstance(data, dict) or set(data) != fields or data['expires_in'] != 1800:
            raise ValueError('Invalid pairing response')
        if not re.fullmatch('[a-f0-9]{32}', data['grant_id']) or data['source_id'] != 'development_computer:'+data['grant_id']:
            raise ValueError('Invalid paired source')
        credential = CaptureCredential(data['key_id'], data['source_id'], bytes.fromhex(data['secret_hex']))
        sender = PinnedCaptureSender('192.168.1.105', 10563, str(DIRECTORY/'ca.crt'), self.pin, credential)
        old = self._pairs.pop(id(connection), None)
        if old:
            await old.sender.close()
        self._pairs = {key: value for key, value in self._pairs.items() if value.expires > self.clock()}
        if len(self._pairs) >= 4:
            raise ValueError('Microphone pairing capacity reached')
        self._pairs[id(connection)] = _Paired(data['grant_id'], data['source_id'], self.clock()+1800, sender)

    def factory(self, connection, conversation_id, start_stage):
        now = self.clock()
        self._runs = {key: value for key, value in self._runs.items() if value[1] > now}
        paired = self._pairs.get(id(connection))
        if not paired or paired.expires <= now or len(self._runs) >= 16:
            return None
        if not conversation_id.startswith('jarvis-voice-v3:development_computer:') or conversation_id in self._runs:
            return None
        tap = ActivatedCaptureTap(paired.source_id, conversation_id, start_stage, paired.sender.submit)
        self._runs[conversation_id] = paired, now+35, tap
        paired.last_result, paired.tap = 'listening', tap
        return tap

    async def context(self, text, conversation_id):
        run = self._runs.pop(conversation_id, None)
        if run is None or run[1] <= self.clock():
            return SpeakerTurn(text, conversation_id)
        paired = run[0]
        member = None
        tap = run[2] if len(run) > 2 else None
        paired.last_result = 'pairing_expired'
        if tap is not None and not tap.submitted:
            paired.last_result = tap.outcome
            identifier = self.turns.route(paired.identifier, conversation_id, None)
            return SpeakerTurn(text, identifier)
        if paired.expires > self.clock():
            try:
                data = await asyncio.wait_for(asyncio.to_thread(self._post, '/consume',
                    {'grant_id': paired.identifier, 'conversation_id': conversation_id}, .7), .75)
                reasons = {'matched', 'voice_uncertain', 'speech_quality_rejected', 'recognizer_unavailable',
                           'calibration_unavailable', 'recognition_timeout', 'already_consumed', 'capacity_reached'}
                if (set(data) == {'member_id', 'personalisation_only', 'reason'}
                        and data['personalisation_only'] is True and data['reason'] in reasons):
                    member = data['member_id'] if data['member_id'] == 'benny' and data['reason'] == 'matched' else None
                    paired.last_result = data['reason']
                else:
                    paired.last_result = 'gateway_unavailable'
            except Exception:
                paired.last_result = 'gateway_unavailable'
        identifier = self.turns.route(paired.identifier, conversation_id, member)
        return SpeakerTurn(text, identifier, member)

    def status(self, connection):
        paired = self._pairs.get(id(connection))
        if paired is None or paired.expires <= self.clock():
            return {'configured': True, 'paired': False, 'expires_in': 0,
                    'last_result': 'pairing_expired' if paired else 'not_paired'}
        result = paired.last_result
        if result == 'listening' and paired.tap is not None:
            if paired.tap.submitted:
                result = 'analysing'
            elif paired.tap._closed:
                result = paired.tap.outcome
        return {'configured': True, 'paired': True, 'expires_in': max(0, int(paired.expires-self.clock())),
                'last_result': result}

    async def close(self):
        self._runs.clear()
        for paired in self._pairs.values():
            await paired.sender.close()
        self._pairs.clear()

    async def unpair(self, connection):
        paired = self._pairs.pop(id(connection), None)
        if paired:
            self._runs = {key: value for key, value in self._runs.items() if value[0] is not paired}
            await paired.sender.close()


@websocket_api.websocket_command({
    vol.Required('type'): 'jarvis_conversation/pair_speaker',
    vol.Required('code'): str,
})
@websocket_api.async_response
async def pair_speaker(hass, connection, msg):
    bridge = hass.data.get('jarvis_conversation', {}).get('speaker_bridge')
    if bridge is None:
        connection.send_error(msg['id'], 'speaker_unavailable', 'Speaker pilot is not configured')
        return
    try:
        await bridge.pair(connection, msg['code'])
        connection.subscriptions[msg['id']] = lambda: hass.async_create_task(bridge.unpair(connection))
        connection.send_result(msg['id'], {'paired': True, 'expires_in': 1800})
    except Exception:
        connection.send_error(msg['id'], 'speaker_pair_failed', 'Use a fresh private operator microphone code')


@websocket_api.websocket_command({vol.Required('type'): 'jarvis_conversation/unpair_speaker'})
@websocket_api.async_response
async def unpair_speaker(hass, connection, msg):
    bridge = hass.data.get('jarvis_conversation', {}).get('speaker_bridge')
    if bridge:
        await bridge.unpair(connection)
    connection.send_result(msg['id'], {'paired': False})


@websocket_api.websocket_command({vol.Required('type'): 'jarvis_conversation/speaker_status'})
@websocket_api.async_response
async def speaker_status(hass, connection, msg):
    bridge = hass.data.get('jarvis_conversation', {}).get('speaker_bridge')
    result = bridge.status(connection) if bridge else {'configured': False, 'paired': False,
                                                       'expires_in': 0, 'last_result': 'not_configured'}
    connection.send_result(msg['id'], result)


async def register(hass):
    websocket_api.async_register_command(hass, pair_speaker)
    websocket_api.async_register_command(hass, unpair_speaker)
    websocket_api.async_register_command(hass, speaker_status)
    domain = hass.data.setdefault('jarvis_conversation', {})
    old = domain.pop('speaker_bridge', None)
    if old:
        await old.close()
    domain.pop('speaker_capture_factory', None)
    def load():
        path = DIRECTORY/'bridge.json'
        if not path.exists():
            return None
        if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_size > 4096:
            raise ValueError('Private speaker configuration required')
        return SpeakerBridge(json.loads(path.read_text()))
    try:
        bridge = await hass.async_add_executor_job(load)
    except Exception:
        bridge = None
    if bridge is not None:
        domain['speaker_bridge'] = bridge
        domain['speaker_capture_factory'] = bridge.factory
