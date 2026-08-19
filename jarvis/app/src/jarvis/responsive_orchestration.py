"""Deadline-aware voice orchestration with bounded Home Assistant follow-up TTS."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import inspect
import re
import time
import uuid


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

    async def execute(self, operation, *, text, conversation_id, source_id, route):
        if not self._valid_route(route) or self.client is None:
            return await operation
        source = str(source_id or conversation_id or "local-default")
        request_key = (source, self._normalise(text))
        existing_id = self._job_by_request.get(request_key)
        existing = self._jobs.get(existing_id) if existing_id else None
        if existing and not existing["task"].done():
            if inspect.iscoroutine(operation):
                operation.close()
            return self._progress(text, existing_id, duplicate=True)

        self._prune()
        task = asyncio.create_task(operation)
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
        }
        self._jobs[job_id] = job
        self._job_by_source[source] = job_id
        self._job_by_request[request_key] = job_id
        asyncio.create_task(self._complete(job))
        progress = self._progress(text, job_id)
        if route.get("event_type"):
            # Browser Assist pipelines can lose their initial TTS when a long
            # intent is still active. A scoped event makes progress audible on
            # the originating satellite without guessing another speaker.
            asyncio.create_task(self._safe_speak(route, progress["message"]))
            progress["direct_delivery"] = True
        return progress

    async def _complete(self, job):
        task = job["task"]
        try:
            result = await asyncio.wait_for(
                asyncio.shield(task), timeout=self.policy.maximum_runtime_seconds
            )
            message = str(result.get("message", "")).strip()
            if not message:
                message = self._actionable_blocker(result)
            await self._speak(job["route"], message)
            if self.logger:
                elapsed = round((self.clock() - job["started"]) * 1000)
                self.logger.info(f"Responsive voice follow-up {job['id']} delivered in {elapsed}ms")
        except asyncio.CancelledError:
            task.cancel()
        except asyncio.TimeoutError:
            task.cancel()
            await self._safe_speak(
                job["route"],
                "This is taking unusually long because a required service is not responding. "
                "Please check the Jarvis diagnostics in Home Assistant.",
            )
        except Exception as error:
            if self.logger:
                self.logger.warning(f"Responsive voice follow-up failed safely: {error}")
            await self._safe_speak(
                job["route"],
                "I could not complete that because a required service failed. "
                "Please check the Jarvis add-on log for the specific cause.",
            )
        finally:
            self._remove(job)

    async def _safe_speak(self, route, message):
        try:
            await self._speak(route, message)
        except Exception as error:
            if self.logger:
                self.logger.warning(
                    f"Responsive voice diagnostic delivery failed safely: {error}"
                )

    async def _speak(self, route, message):
        spoken = self._spoken(message)
        if route.get("event_type"):
            await self.client.dispatch_event(
                route["event_type"],
                {
                    "message": spoken,
                    "source_id": str(route.get("source_id", ""))[:200],
                    "target_id": str(route.get("target_id", ""))[:200],
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
            messages = ("Analyzing.", "Processing.", "Working.")
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
            oldest["task"].cancel()
            self._remove(oldest)
