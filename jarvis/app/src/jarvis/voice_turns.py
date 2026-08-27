"""Opt-in voice transport: one turn, one destination, one final answer.

No raw model fragments cross this boundary. Only the completed application
response is eligible for speech; intermediate reasoning cannot become audio.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from contextvars import ContextVar
import hashlib
import re
import time

from jarvis.sentence_stream import sentence_sink
from jarvis.personality_presentation import sanitize_spoken_response

reliable_turn = ContextVar("reliable_voice_turn", default=False)


def is_follow_up(text):
    return bool(re.search(
        r"^(?:and\s+)?(?:tell me more|more detail|go deeper|elaborate|expand(?: on that)?|"
        r"what about\b|how about\b|why is that|how does (?:it|that)\b|"
        r"which (?:one|of (?:those|them))\b)", str(text).strip(), re.I))


class VoiceTurnController:
    """Retain idempotency independently from answer/context caches.

    A superseded operation is allowed to finish under its conversation lock:
    cancelling a Python thread does not cancel its model or HA operation.
    Its audio is discarded. This avoids claiming a home action was cancelled.
    """

    def __init__(self, client, logger=None, *, deadline=1.0, capacity=16):
        self.client, self.logger = client, logger
        self.deadline, self.capacity = deadline, capacity
        self.turns = OrderedDict()
        self.active = {}

    async def execute(self, operation, *, route, conversation_id):
        for old_key, item in list(self.turns.items()):
            if item["done"] and time.monotonic() - item["started"] > 1200:
                self.turns.pop(old_key)
        request = str(route["request_id"])
        endpoint = str(route["target_id"])
        key = (conversation_id, request)
        if key in self.turns:
            operation.close()
            return {"status": "in_progress", "message": "", "voice_protocol": 2}
        live = sum(not item["done"] for item in self.turns.values())
        if live >= self.capacity:
            operation.close()
            raise RuntimeError("Jarvis voice capacity reached; wait for active requests to finish")
        turn = dict(route=route.copy(), conversation=conversation_id, request=request,
                    key=key, endpoint=endpoint, sequence=0, done=False,
                    started=time.monotonic(), events=[])
        self.turns[key] = turn
        self.active[endpoint] = key
        token = reliable_turn.set(True)
        sink = sentence_sink.set(None)
        try:
            turn["task"] = asyncio.create_task(self._run(operation, turn))
        finally:
            sentence_sink.reset(sink)
            reliable_turn.reset(token)
        return {"status": "in_progress", "message": "", "voice_protocol": 2}

    async def _run(self, operation, turn):
        task = asyncio.create_task(operation)
        try:
            done, _ = await asyncio.wait({task}, timeout=self.deadline)
            if not done:
                try:
                    await self._emit(turn, "progress", "Request received.")
                except Exception:
                    # A failed progress transport must never abandon the answer.
                    pass
            result = await task
            message = sanitize_spoken_response(str(result.get("message") or "A required service returned no answer. Check the Jarvis log and integration status."))
            await self._emit(turn, "final", message)
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception as error:
            if self.logger:
                self.logger.warning(f"Voice turn {turn['request']} failed: {type(error).__name__}")
            try:
                await self._emit(turn, "final", "A required service failed. Check the Jarvis log and the Home Assistant integration status.")
            except Exception:
                turn["delivery_error"] = "Home Assistant event transport unavailable"
        finally:
            turn["done"] = True
            if self.active.get(turn["endpoint"]) == turn["key"]:
                self.active.pop(turn["endpoint"], None)
            for key in list(self.turns):
                if len(self.turns) <= 128:
                    break
                if self.turns[key]["done"]:
                    self.turns.pop(key)

    async def _emit(self, turn, stage, message):
        if self.active.get(turn["endpoint"]) != turn["key"]:
            return
        turn["sequence"] += 1
        payload = dict(protocol=2, request_id=turn["request"],
                       conversation_id=turn["route"]["wire_conversation_id"],
                       target_id=turn["endpoint"], stage=stage,
                       sequence=turn["sequence"], message=message,
                       delivery_id=f"{turn['request']}:{turn['sequence']}")
        for attempt in range(4):
            if self.active.get(turn["endpoint"]) != turn["key"]:
                return
            try:
                await self.client.dispatch_event("jarvis_voice_follow_up", payload)
                break
            except Exception:
                if attempt == 3:
                    turn["delivery_error"] = "Home Assistant event transport unavailable"
                    raise
                await asyncio.sleep(2 ** attempt)
        turn["events"].append({**payload, "dispatched_ms": round((time.monotonic() - turn["started"]) * 1000)})
        if self.logger:
            digest = hashlib.sha256(message.encode()).hexdigest()[:16]
            elapsed = round((time.monotonic() - turn["started"]) * 1000)
            self.logger.info(f"Voice turn={turn['request']} stage={stage} text_hash={digest} dispatched_ms={elapsed}")

    async def inspect(self, request_id):
        """Authenticated inspection only; dispatch is not playback acknowledgement."""
        for turn in self.turns.values():
            if turn["request"] == request_id and time.monotonic() - turn["started"] <= 1200:
                return {"request_id": request_id, "done": turn["done"], "events": list(turn["events"]), "delivery_error": turn.get("delivery_error")}
        return {"request_id": request_id, "state": "unknown_or_expired"}
