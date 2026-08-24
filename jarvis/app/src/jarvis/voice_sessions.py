"""Unified, privacy-safe voice endpoint and session coordination."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import time
import uuid


@dataclass(frozen=True, slots=True)
class VoiceEndpoint:
    source_id: str
    target_id: str
    room_id: str
    event_type: str | None = None
    tts_entity_id: str | None = None
    media_player_entity_id: str | None = None

    @classmethod
    def from_route(cls, source_id, route):
        source = str(source_id or route.get("source_id") or "local-default")[:200]
        media = str(route.get("media_player_entity_id") or "")[:200]
        target = str(route.get("target_id") or media or source)[:200]
        return cls(source, target, str(route.get("room_id") or "")[:100],
                   route.get("event_type"), route.get("tts_entity_id"), media or None)


@dataclass(slots=True)
class VoiceSession:
    session_id: str
    conversation_id: str
    endpoint: VoiceEndpoint
    started_at: float
    sequence: int = 0
    state: str = "active"


class VoiceSessionCoordinator:
    """Own endpoint identity, ordered delivery leases, and bounded diagnostics."""

    def __init__(self, *, clock=time.monotonic, maximum_sessions=64):
        self.clock = clock
        self.maximum_sessions = maximum_sessions
        self._sessions = {}
        self._leases = {}
        self._diagnostics = deque(maxlen=200)

    def open(self, conversation_id, source_id, route):
        endpoint = VoiceEndpoint.from_route(source_id, route)
        key = (str(conversation_id or "local-default"), endpoint.source_id)
        session = self._sessions.get(key)
        if session is None or session.state != "active":
            session = VoiceSession(uuid.uuid4().hex, key[0], endpoint, self.clock())
            self._sessions[key] = session
        else:
            session.endpoint = endpoint
        while len(self._sessions) > self.maximum_sessions:
            self._sessions.pop(next(iter(self._sessions)))
        return session

    def next_delivery(self, session):
        session.sequence += 1
        return f"{session.session_id}:{session.sequence}", session.sequence

    def lease(self, endpoint):
        return self._leases.setdefault(endpoint.target_id, asyncio.Lock())

    def record(self, session, status, duration_ms=0):
        self._diagnostics.append({
            "session_id": session.session_id,
            "source_present": bool(session.endpoint.source_id),
            "target_present": bool(session.endpoint.target_id),
            "room_present": bool(session.endpoint.room_id),
            "status": str(status), "duration_ms": int(duration_ms),
        })

    def diagnostics(self):
        return tuple(dict(item) for item in self._diagnostics)
