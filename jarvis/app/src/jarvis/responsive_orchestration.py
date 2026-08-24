"""Deadline-aware voice orchestration with bounded Home Assistant follow-up TTS."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import inspect
import re
import time
import uuid

from jarvis.sentence_stream import sentence_sink
from jarvis.voice_sessions import VoiceSessionCoordinator


@dataclass(frozen=True, slots=True)
class ResponsiveVoicePolicy:
    progress_deadline_seconds: float = 1.0
    maximum_runtime_seconds: float = 90.0
    maximum_pending_jobs: int = 16

    @classmethod
    def from_config(cls, value):
        config = {} if value is None else value
        if not isinstance(config, dict):
            raise ValueError("responsive_voice must be a mapping")
        policy = cls(**{
            name: config.get(name, getattr(cls(), name))
            for name in cls.__dataclass_fields__
        })
        if not 1.0 <= policy.progress_deadline_seconds <= 4.0:
            raise ValueError("responsive_voice.progress_deadline_seconds is invalid")
        if not 10.0 <= policy.maximum_runtime_seconds <= 300.0:
            raise ValueError("responsive_voice.maximum_runtime_seconds is invalid")
        if not 1 <= policy.maximum_pending_jobs <= 64:
            raise ValueError("responsive_voice.maximum_pending_jobs is invalid")
        return policy


class ResponsiveVoiceCoordinator:
    """Return promptly, then deliver the completed result to an explicit HA route."""

    def __init__(self, policy=None, *, client=None, logger=None, clock=time.monotonic):
        self.policy = policy or ResponsiveVoicePolicy()
        self.client = client
        self.logger = logger
        self.clock = clock
        self._jobs: dict[str, dict[str, object]] = {}
        self._job_by_source: dict[str, str] = {}
        self._job_by_request: dict[tuple[str, str], str] = {}
        self._progress_sequence = 0
        self.sessions = VoiceSessionCoordinator(clock=clock)

    async def execute(self, operation, *, text, conversation_id, source_id, route):
        if not self._valid_route(route) or self.client is None:
            return await operation
        source = str(source_id or conversation_id or "local-default")
        session = self.sessions.open(conversation_id, source, route)
        request_key = (source, self._normalise(text))
        existing_id = self._job_by_request.get(request_key)
        existing = self._jobs.get(existing_id) if existing_id else None
        if existing and not existing["task"].done():
            if inspect.iscoroutine(operation):
                operation.close()
            return self._progress(text, existing_id, duplicate=True)

        self._prune()
        loop = asyncio.get_running_loop()
        stream_state = {"enabled": False, "pending": [], "streamed": False}

        def stream_sentence(sentence):
            value = self._spoken(sentence)
            if not value:
                return
            if not stream_state["enabled"]:
                stream_state["pending"].append(value)
                return
            # Mark delivery before queueing back onto the event loop. The
            # model worker can finish immediately after emitting its final
            # sentence; without this guard _complete may also speak the full
            # answer before the queued sentence callback runs.
            stream_state["streamed"] = True
            def deliver():
                asyncio.create_task(self._safe_speak(route, value, session=session))
            loop.call_soon_threadsafe(deliver)

        token = sentence_sink.set(stream_sentence)
        try:
            task = asyncio.create_task(operation)
        finally:
            sentence_sink.reset(token)
        done, _ = await asyncio.wait(
            {task}, timeout=self.policy.progress_deadline_seconds
        )
        if done:
            return await task

        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "task": task,
            "route": dict(route),
            "source": source,
            "request_key": request_key,
            "started": self.clock(),
            "stream_state": stream_state,
            "session": session,
        }
        self._jobs[job_id] = job
        self._job_by_source[source] = job_id
        self._job_by_request[request_key] = job_id
        asyncio.create_task(self._complete(job))
        stream_state["enabled"] = True
        pending = stream_state["pending"]
        progress = self._progress(text, job_id)
        if pending:
            progress["message"] = pending.pop(0)
            stream_state["streamed"] = True
            for sentence in pending:
                asyncio.create_task(self._safe_speak(route, sentence, session=session))
            pending.clear()
        return progress

    async def _complete(self, job):
        task = job["task"]
        try:
            while True:
                done, _ = await asyncio.wait(
                    {task}, timeout=self.policy.maximum_runtime_seconds
                )
                if done:
                    result = await task
                    break
                await self._safe_speak(
                    job["route"],
                    "Still working. A required service is responding slowly.",
                    session=job["session"],
                )
            message = str(result.get("message", "")).strip()
            if not message:
                message = self._actionable_blocker(result)
            if not job.get("stream_state", {}).get("streamed"):
                await self._speak(job["route"], message, session=job["session"])
            if self.logger:
                elapsed = round((self.clock() - job["started"]) * 1000)
                self.logger.info(f"Responsive voice follow-up {job['id']} delivered in {elapsed}ms")
        except asyncio.CancelledError:
            task.cancel()
        except Exception as error:
            if self.logger:
                self.logger.warning(f"Responsive voice follow-up failed safely: {error}")
            await self._safe_speak(
                job["route"],
                "I could not complete that because a required service failed. "
                "Please check the Jarvis add-on log for the specific cause.",
                session=job["session"],
            )
        finally:
            self._remove(job)

    async def _safe_speak(self, route, message, session=None):
        try:
            await self._speak(route, message, session=session)
        except Exception as error:
            if self.logger:
                self.logger.warning(
                    f"Responsive voice diagnostic delivery failed safely: {error}"
                )

    async def _speak(self, route, message, session=None):
        spoken = self._spoken(message)
        session = session or self.sessions.open("delivery", route.get("source_id"), route)
        delivery_id, sequence = self.sessions.next_delivery(session)
        started = self.clock()
        async with self.sessions.lease(session.endpoint):
            await self._deliver(route, spoken, session, delivery_id, sequence)
        self.sessions.record(session, "delivered", round((self.clock() - started) * 1000))

    async def _deliver(self, route, spoken, session, delivery_id, sequence):
        if route.get("event_type"):
            await self.client.dispatch_event(
                route["event_type"],
                {
                    "message": spoken,
                    "source_id": str(route.get("source_id", ""))[:200],
                    "target_id": str(route.get("target_id", ""))[:200],
                    "session_id": session.session_id,
                    "delivery_id": delivery_id,
                    "sequence": sequence,
                },
            )
            return
        data = {
            "entity_id": route["tts_entity_id"],
            "media_player_entity_id": route["media_player_entity_id"],
            "message": spoken,
            "cache": True,
        }
        if route.get("language"):
            data["language"] = route["language"]
        if route.get("voice"):
            data["options"] = {"voice": route["voice"]}
        try:
            await self._call_tts(data)
        except Exception:
            if "language" not in data and "options" not in data:
                raise
            data.pop("language", None)
            data.pop("options", None)
            await self._call_tts(data)

    async def _call_tts(self, data):
        dispatcher = getattr(self.client, "dispatch_service", None)
        if dispatcher is not None:
            completion = await dispatcher("tts", "speak", data)
            await completion
            return
        await self.client.call_service("tts", "speak", data)

    def _progress(self, text, job_id, duplicate=False):
        lower = text.casefold()
        self._progress_sequence += 1
        if any(word in lower for word in ("latest", "current", "today", "search", "release")):
            messages = ("Searching sources.", "Verifying data.", "Querying databases.")
        elif any(word in lower for word in ("calculate", "compute", "count", "convert", "equation")):
            messages = ("Calculating.", "Computing.", "Processing figures.")
        elif any(word in lower for word in ("why", "explain", "compare", "plan", "analyse", "analyze")):
            messages = ("Working.", "Checking.", "One moment.")
        else:
            messages = ("Processing.", "Working.", "One moment.")
        message = messages[(self._progress_sequence - 1) % len(messages)]
        return {
            "status": "in_progress",
            "message": message,
            "follow_up_id": job_id,
            "duplicate": duplicate,
        }

    @staticmethod
    def _actionable_blocker(result):
        status = str(result.get("status", "unavailable"))
        if status == "forbidden":
            return "I cannot complete that because Home Assistant has not authorised it. Please review Jarvis entity and service permissions."
        if status == "not_supported":
            return "That capability is not configured yet. Please review the Jarvis integration and add-on configuration."
        return "A required service did not provide an answer. Please check the Jarvis add-on log and the relevant Home Assistant integration."

    @staticmethod
    def _spoken(message):
        text = re.sub(r"\[([^]]+)\]\(https?://[^)]+\)", r"\1", str(message))
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"[*#>`_]+", "", text)
        return " ".join(text.split())[:700].strip()

    @staticmethod
    def _normalise(text):
        return " ".join(str(text).casefold().strip(" .?!").split())

    @staticmethod
    def _valid_route(route):
        return bool(
            isinstance(route, dict)
            and (
                route.get("event_type")
                or (
                    route.get("tts_entity_id")
                    and route.get("media_player_entity_id")
                )
            )
        )

    def _remove(self, job):
        self._jobs.pop(job["id"], None)
        if self._job_by_source.get(job["source"]) == job["id"]:
            self._job_by_source.pop(job["source"], None)
        if self._job_by_request.get(job["request_key"]) == job["id"]:
            self._job_by_request.pop(job["request_key"], None)

    def _prune(self):
        finished = [job for job in self._jobs.values() if job["task"].done()]
        for job in finished:
            self._remove(job)
        while len(self._jobs) >= self.policy.maximum_pending_jobs:
            oldest = min(self._jobs.values(), key=lambda item: item["started"])
            if oldest["task"].done():
                self._remove(oldest)
                continue
            break
