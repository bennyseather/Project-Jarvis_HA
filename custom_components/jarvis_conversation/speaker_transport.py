"""Bounded, authenticated speaker PCM transport; NOT an enabled service.

TLS validates a dedicated CA/hostname AND a pinned certificate. HMAC is a
separate per-source capture credential, not an administrator/enrolment grant.
No redirects, proxies, plaintext transport, speaker labels or quality flags.
Only a future reviewed server installer may open a production listener.
"""
import asyncio
from dataclasses import dataclass, field
import hashlib
import hmac
import ipaddress
import json
import math
import re
import secrets
import ssl
import struct
import threading
import time

from .speaker_capture import CapturedUtterance, MAX_AUDIO_BYTES, bounded_id

MAGIC = b'JSP1'
MAX_HEADER = 2048
MAX_PACKET = 4 + 4 + MAX_HEADER + MAX_AUDIO_BYTES + 32


@dataclass(frozen=True)
class CaptureCredential:
    key_id: str
    source_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self):
        bounded_id(self.key_id)
        bounded_id(self.source_id)
        if type(self.secret) is not bytes or len(self.secret) != 32:
            raise ValueError('Dedicated 256-bit capture credential required')


def sign_capture(capture, credential, challenge):
    if type(challenge) is not bytes or len(challenge) != 32:
        raise ValueError('Fresh connection challenge required')
    if not isinstance(capture, CapturedUtterance): raise TypeError('Trusted captured utterance required')
    if capture.source_id != credential.source_id: raise PermissionError('Wrong source credential')
    for value in (capture.request_id, capture.conversation_id, capture.source_id): bounded_id(value)
    if type(capture.captured_at) not in (int, float) or not math.isfinite(capture.captured_at):
        raise ValueError('Invalid capture time')
    if type(capture.pcm16) is not bytes or not 64000 <= len(capture.pcm16) <= MAX_AUDIO_BYTES or len(capture.pcm16) % 2:
        raise ValueError('Invalid capture audio')
    header = json.dumps({'version': 1, 'purpose': 'recognise', 'key_id': credential.key_id,
                         'challenge': challenge.hex(),
                         'source_id': capture.source_id, 'request_id': capture.request_id,
                         'conversation_id': capture.conversation_id, 'captured_at': capture.captured_at,
                         'format': 'pcm16le-16000-mono', 'audio_bytes': len(capture.pcm16)},
                        sort_keys=True, allow_nan=False, separators=(',', ':')).encode()
    if len(header) > MAX_HEADER: raise ValueError('Oversized capture metadata')
    packet = MAGIC + struct.pack('!I', len(header)) + header + capture.pcm16
    return packet + hmac.digest(credential.secret, packet, 'sha256')


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result: raise ValueError('Duplicate field')
        result[name] = value
    return result


class CaptureVerifier:
    def __init__(self, credentials, *, wall_clock=time.time, clock=time.monotonic):
        if not 1 <= len(credentials) <= 16: raise ValueError('Explicit paired sources required')
        self.credentials = {item.key_id: item for item in credentials}
        if len(self.credentials) != len(credentials): raise ValueError('Duplicate key identifier')
        self.wall_clock, self.clock = wall_clock, clock
        self._seen = {}
        self._lock = threading.Lock()
        self._booted_at = wall_clock()

    def verify(self, packet, challenge):
        if type(challenge) is not bytes or len(challenge) != 32:
            raise ValueError('Fresh connection challenge required')
        if type(packet) is not bytes or not 40 <= len(packet) <= MAX_PACKET or packet[:4] != MAGIC:
            raise ValueError('Invalid capture packet')
        size = struct.unpack('!I', packet[4:8])[0]
        if not 0 < size <= MAX_HEADER or len(packet) < 8 + size + 32: raise ValueError('Invalid header length')
        header = json.loads(packet[8:8+size], object_pairs_hook=_unique_object)
        fields = {'version', 'purpose', 'key_id', 'source_id', 'request_id', 'conversation_id', 'challenge',
                  'captured_at', 'format', 'audio_bytes'}
        if not isinstance(header, dict) or set(header) != fields: raise ValueError('Unexpected capture fields')
        credential = self.credentials.get(header['key_id']) if type(header['key_id']) is str else None
        if credential is None or not hmac.compare_digest(hmac.digest(credential.secret, packet[:-32], 'sha256'), packet[-32:]):
            raise PermissionError('Unauthenticated capture')
        if type(header['challenge']) is not str or not hmac.compare_digest(header['challenge'], challenge.hex()):
            raise PermissionError('Wrong connection challenge')
        if (type(header['version']) is not int or header['version'] != 1 or header['purpose'] != 'recognise'
                or header['format'] != 'pcm16le-16000-mono' or header['source_id'] != credential.source_id):
            raise PermissionError('Wrong capture scope')
        for name in ('request_id', 'conversation_id', 'source_id'): bounded_id(header[name])
        raw = packet[8+size:-32]
        if (type(header['audio_bytes']) is not int or header['audio_bytes'] != len(raw)
                or not 64000 <= len(raw) <= MAX_AUDIO_BYTES or len(raw) % 2): raise ValueError('Invalid audio size')
        timestamp = header['captured_at']
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp): raise ValueError('Invalid timestamp')
        now = self.wall_clock()
        # Fresh per-connection challenge prevents wire replay across restart or
        # clock rollback. The time window additionally rejects delayed captures.
        if not -1 <= now - timestamp <= 5 or timestamp < self._booted_at:
            raise ValueError('Expired capture')
        with self._lock:
            monotonic = self.clock()
            self._seen = {key: expiry for key, expiry in self._seen.items() if expiry > monotonic}
            key = (credential.key_id, header['request_id'])
            if key in self._seen: raise ValueError('Replayed capture')
            if len(self._seen) >= 256: raise ValueError('Capture capacity reached')
            self._seen[key] = monotonic + 7
        return CapturedUtterance(header['request_id'], header['conversation_id'], header['source_id'], timestamp, raw)


async def _read_frame(reader, limit):
    size = struct.unpack('!I', await reader.readexactly(4))[0]
    if not 0 < size <= limit: raise ValueError('Oversized frame')
    return await reader.readexactly(size)


async def _write_frame(writer, body):
    writer.write(struct.pack('!I', len(body)) + body)
    await writer.drain()


class PinnedCaptureSender:
    """One in-flight send, no queue or retries. Caller owns event loop lifetime."""
    def __init__(self, address, port, ca_file, certificate_sha256, credential, *, timeout=.9):
        self.address = str(ipaddress.ip_address(address))
        if type(port) is not int or not 1 <= port <= 65535: raise ValueError('Invalid configured port')
        if not re.fullmatch('[a-f0-9]{64}', certificate_sha256): raise ValueError('Pinned certificate required')
        if type(timeout) not in (int, float) or not .05 <= timeout <= 2: raise ValueError('Invalid transport budget')
        self.port, self.fingerprint, self.credential, self.timeout = port, certificate_sha256, credential, timeout
        self.ssl = ssl.create_default_context(cafile=ca_file)
        self.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
        self._task = None
        self.last_status = 'idle'

    def submit(self, capture):
        if self._task is not None and not self._task.done(): return False
        self._task = asyncio.create_task(self._send(capture))
        return True

    async def _send(self, capture):
        writer = None
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_connection(self.address, self.port, ssl=self.ssl,
                    server_hostname=self.address, ssl_handshake_timeout=self.timeout, limit=4096)
                certificate = writer.get_extra_info('ssl_object').getpeercert(binary_form=True)
                if not hmac.compare_digest(hashlib.sha256(certificate).hexdigest(), self.fingerprint):
                    raise PermissionError('Certificate pin mismatch')
                challenge = await _read_frame(reader, 32)
                packet = sign_capture(capture, self.credential, challenge)
                await _write_frame(writer, packet)
                reply = json.loads(await _read_frame(reader, 1024), object_pairs_hook=_unique_object)
                if set(reply) != {'request_id', 'status'} or reply['request_id'] != capture.request_id:
                    raise ValueError('Wrong capture acknowledgement')
                if reply['status'] not in ('accepted', 'unavailable', 'rejected', 'busy'):
                    raise ValueError('Invalid status')
                self.last_status = reply['status']
        except asyncio.CancelledError:
            self.last_status = 'cancelled'
            raise
        except Exception:
            self.last_status = 'unavailable'  # no paths, PCM, secrets or exception details
        finally:
            if writer is not None:
                writer.close()
                # Abort rather than await an unbounded TLS shutdown from a stuck peer.
                writer.transport.abort()

    async def close(self):
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None


class CaptureReceiver:
    """TLS callback for a future private service; constructing it opens no port.

    process must be a non-blocking async adapter with its own worker limits.
    A cancellation-resistant callback keeps the single slot occupied; it cannot
    produce a late acknowledgement or accumulate an unbounded queue of jobs.
    The default caller/service may reject everything until quality is configured.
    No identity/result detail is returned to the microphone sender.
    """
    def __init__(self, verifier, process, *, timeout=1.):
        if type(timeout) not in (int, float) or not .05 <= timeout <= 2:
            raise ValueError('Invalid receiver budget')
        self.verifier, self.process, self.timeout = verifier, process, timeout
        self._busy = False
        self._processing = None

    @staticmethod
    def _consume(task):
        if not task.cancelled(): task.exception()

    async def handle(self, reader, writer):
        if (self._busy or (self._processing is not None and not self._processing.done())
                or writer.get_extra_info('ssl_object') is None):
            writer.close()
            writer.transport.abort()
            return
        self._busy = True
        try:
            async with asyncio.timeout(self.timeout):
                challenge = secrets.token_bytes(32)
                await _write_frame(writer, challenge)
                packet = await _read_frame(reader, MAX_PACKET)
                capture = self.verifier.verify(packet, challenge)
                self._processing = asyncio.create_task(self.process(capture))
                self._processing.add_done_callback(self._consume)
                # Shield only keeps the task handle under our ownership; the
                # request deadline cancels it below without awaiting an unbounded
                # cancellation handshake from an unhealthy optional backend.
                status = await asyncio.shield(self._processing)
                if status not in ('accepted', 'unavailable', 'rejected', 'busy'): status = 'unavailable'
                await _write_frame(writer, json.dumps({'request_id': capture.request_id, 'status': status}).encode())
        except Exception:
            pass  # unauthenticated/malformed requests receive no diagnostic oracle
        finally:
            if self._processing is not None and not self._processing.done():
                self._processing.cancel()
            self._busy = False
            writer.close()
            writer.transport.abort()
