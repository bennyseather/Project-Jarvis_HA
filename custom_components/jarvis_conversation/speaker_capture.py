"""Optional in-memory observer of server-owned HA pipeline events.

Standalone standard-library module, also packaged with the HA integration. A
trusted factory must bind source/session before construction. Browser message
fields do NOT authenticate a microphone or an administrator. Never observes
pre-wake audio, never alters the original stream, never awaits the sender.
"""
from dataclasses import dataclass, field
import math
import re
import secrets
import time

MAX_AUDIO_BYTES = 960000
MAX_CHUNK_BYTES = 32768


def bounded_id(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value):
        raise ValueError('Invalid capture binding')
    return value


@dataclass(frozen=True)
class CapturedUtterance:
    request_id: str
    conversation_id: str
    source_id: str
    captured_at: float  # issuer wall clock, used only for authenticated transport freshness
    pcm16: bytes = field(repr=False)


class ActivatedCaptureTap:
    def __init__(self, source_id, conversation_id, start_stage, submit, *,
                 clock=time.monotonic, wall_clock=time.time):
        self.source_id = bounded_id(source_id)
        self.conversation_id = bounded_id(conversation_id)
        if start_stage not in ('stt', 'wake_word'): raise ValueError('Audio stage required')
        self.request_id = secrets.token_hex(16)  # server generated, not browser supplied
        self.submit, self.clock, self.wall_clock = submit, clock, wall_clock
        self._activated = start_stage == 'stt'  # validated PTT/follow-up start
        self._collecting = False
        self._closed = False
        self._voiced = False
        self._started = None
        self._buffer = bytearray()
        self.submitted = False
        self.outcome = 'waiting_for_speech'

    def abort(self, reason='cancelled'):
        if not self._closed:
            self.outcome = reason
        self._closed = True
        self._collecting = False
        self._buffer.clear()

    def expire(self):
        """Called by the owning pipeline's timer, even when no audio arrives."""
        if self._started is not None and not 0 <= self.clock() - self._started <= 35:
            self.abort('expired')

    def _seal(self):
        if not self._collecting or not self._voiced:
            self.abort('speech_not_confirmed')
            return
        raw = bytes(self._buffer)
        elapsed = self.clock() - self._started
        self.abort('audio_too_short')
        if not 0 <= elapsed <= 35:
            self.outcome = 'expired'
            return
        if not 64000 <= len(raw) <= MAX_AUDIO_BYTES:
            return
        timestamp = self.wall_clock()
        if not math.isfinite(timestamp):
            self.outcome = 'invalid_audio'
            return
        capture = CapturedUtterance(self.request_id, self.conversation_id, self.source_id, timestamp, raw)
        try:
            self.submitted = self.submit(capture) is True
        except Exception:
            self.submitted = False
        self.outcome = 'submitted' if self.submitted else 'sender_unavailable'

    def on_event(self, event):
        if self._closed: return
        kind = event.get('type') if isinstance(event, dict) else getattr(event, 'type', None)
        if kind == 'wake_word-end':
            self._activated = True
        elif kind == 'stt-start':
            if not self._activated or self._collecting:
                self.abort()
                return
            self._collecting = True
            self._started = self.clock()
            self.outcome = 'collecting'
        elif kind == 'stt-vad-start':
            if self._collecting: self._voiced = True
        elif kind in ('stt-vad-end', 'stt-end'):
            # HA may finish successful STT before its external VAD emits an end.
            # Both boundaries are server-owned; speech start is still required.
            # Node independently measures speech/overlap/quality before matching.
            self._seal()
        elif kind in ('intent-start', 'tts-start', 'run-end', 'error'):
            self.abort()

    def feed(self, chunk):
        if self._closed or not self._collecting: return
        if (type(chunk) not in (bytes, bytearray) or not chunk or len(chunk) % 2
                or len(chunk) > MAX_CHUNK_BYTES or len(self._buffer) + len(chunk) > MAX_AUDIO_BYTES
                or not 0 <= self.clock() - self._started <= 35):
            self.abort('invalid_audio')
            return
        self._buffer.extend(chunk)
