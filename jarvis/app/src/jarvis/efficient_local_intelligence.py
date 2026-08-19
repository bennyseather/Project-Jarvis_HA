"""Bounded, privacy-safe orchestration for efficient local intelligence."""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass
import hashlib
import re
import time


@dataclass(frozen=True, slots=True)
class EfficientIntelligencePolicy:
    enabled: bool = True
    stable_cache_ttl_seconds: int = 600
    maximum_cache_entries: int = 128
    maximum_concurrent_reasoning: int = 2
    maximum_context_references: int = 24
    telemetry_entries: int = 200

    @classmethod
    def from_config(cls, value):
        config = {} if value is None else value
        if not isinstance(config, dict):
            raise ValueError("efficient_intelligence must be a mapping")
        policy = cls(**{
            name: config.get(name, getattr(cls(), name))
            for name in cls.__dataclass_fields__
        })
        if not 30 <= policy.stable_cache_ttl_seconds <= 3600:
            raise ValueError("efficient_intelligence.stable_cache_ttl_seconds is invalid")
        if not 8 <= policy.maximum_cache_entries <= 1024:
            raise ValueError("efficient_intelligence.maximum_cache_entries is invalid")
        if not 1 <= policy.maximum_concurrent_reasoning <= 8:
            raise ValueError("efficient_intelligence.maximum_concurrent_reasoning is invalid")
        if not 4 <= policy.maximum_context_references <= 100:
            raise ValueError("efficient_intelligence.maximum_context_references is invalid")
        if not 20 <= policy.telemetry_entries <= 1000:
            raise ValueError("efficient_intelligence.telemetry_entries is invalid")
        return policy


class EfficientLocalIntelligence:
    """Measure routes, bound costly work, and cache only stable safe answers."""

    _CURRENT = re.compile(
        r"\b(latest|newest|current|today|tonight|recent|release[ds]?|price|schedule|"
        r"president|prime minister|office.?holder|weather|news)\b", re.I
    )
    _HOME = re.compile(
        r"\b(turn|switch|set|dim|open|close|lock|unlock|temperature|humidity|"
        r"light|lamp|thermostat|sensor|door|window|scene|automation|home assistant)\b", re.I
    )
    _PERSONAL = re.compile(
        r"\b(my|me|i|we|our|remember|forget|learned|calendar|appointment|password|pin)\b", re.I
    )
    _STABLE_QUESTION = re.compile(
        r"^(what|why|how|who|where|when|explain|compare|define|calculate|convert)\b", re.I
    )

    def __init__(self, policy=None, *, clock=time.monotonic, logger=None):
        self.policy = policy or EfficientIntelligencePolicy()
        self.clock = clock
        self.logger = logger
        self._cache = OrderedDict()
        self._telemetry = deque(maxlen=self.policy.telemetry_entries)
        self._reasoning_slots = asyncio.Semaphore(
            self.policy.maximum_concurrent_reasoning
        )

    async def execute(self, operation, *, text, source_id=None):
        route = self.classify(text)
        cacheable = self._cacheable(text, route)
        key = self._key(text) if cacheable else None
        started = self.clock()
        cached = self._cache_get(key) if key else None
        if cached is not None:
            result = dict(cached)
            result["cache"] = "hit"
            self._record(route, "hit", result, started, source_id)
            if asyncio.iscoroutine(operation):
                operation.close()
            return result

        if route == "general_reasoning":
            async with self._reasoning_slots:
                result = await operation
        else:
            result = await operation
        actual_route = self._actual_route(route, result)
        if key and actual_route == "general_reasoning" and result.get("status") == "success":
            self._cache_put(key, result)
        result = dict(result)
        result.setdefault("cache", "miss" if cacheable else "bypass")
        self._record(actual_route, result["cache"], result, started, source_id)
        return result

    def classify(self, text):
        value = " ".join(str(text).split())
        if self._HOME.search(value):
            return "home_assistant"
        if self._CURRENT.search(value):
            return "current_information"
        if self._PERSONAL.search(value):
            return "memory_knowledge"
        return "general_reasoning"

    def context_for(self, text, references):
        """Return only relevant authorized metadata; never entity state/history."""
        if not isinstance(references, dict):
            return {}
        tokens = set(re.findall(r"[a-z0-9]+", str(text).casefold()))
        limit = self.policy.maximum_context_references
        selected = {}
        for category, values in references.items():
            candidates = tuple(str(value) for value in values)
            ranked = sorted(
                candidates,
                key=lambda value: (
                    -len(tokens.intersection(re.findall(r"[a-z0-9]+", value.casefold()))),
                    value.casefold(),
                ),
            )
            matches = [value for value in ranked if tokens.intersection(
                re.findall(r"[a-z0-9]+", value.casefold())
            )]
            selected[category] = tuple((matches or ranked)[:limit])
        return selected

    def diagnostics(self):
        return tuple(dict(item) for item in self._telemetry)

    def _cacheable(self, text, route):
        value = " ".join(str(text).casefold().split()).strip(" .?!")
        return bool(
            route == "general_reasoning"
            and self._STABLE_QUESTION.search(value)
            and not self._CURRENT.search(value)
            and not self._HOME.search(value)
            and not self._PERSONAL.search(value)
        )

    @staticmethod
    def _key(text):
        normalized = " ".join(str(text).casefold().split()).strip(" .?!")
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _cache_get(self, key):
        item = self._cache.get(key)
        if item is None:
            return None
        expires, result = item
        if expires <= self.clock():
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return result

    def _cache_put(self, key, result):
        safe = {
            name: value for name, value in result.items()
            if name in {"status", "message", "provider", "model"}
        }
        self._cache[key] = (
            self.clock() + self.policy.stable_cache_ttl_seconds,
            safe,
        )
        self._cache.move_to_end(key)
        while len(self._cache) > self.policy.maximum_cache_entries:
            self._cache.popitem(last=False)

    @staticmethod
    def _actual_route(route, result):
        provider = str(result.get("provider", "")).casefold()
        if provider == "current_information" or result.get("sources"):
            return "current_information"
        if result.get("action_payload") or result.get("confirmation_token"):
            return "home_assistant"
        return route

    def _record(self, route, cache, result, started, source_id):
        # Deliberately excludes utterance, answer, entity IDs, and conversation IDs.
        diagnostic = {
            "route": route,
            "cache": cache,
            "provider": str(result.get("provider", "deterministic"))[:40],
            "model": str(result.get("model", "none"))[:60],
            "duration_ms": min(300000, max(0, round((self.clock() - started) * 1000))),
            "source_present": bool(source_id),
            "status": str(result.get("status", "unknown"))[:40],
        }
        self._telemetry.append(diagnostic)
        if self.logger:
            self.logger.info(
                "Efficient intelligence route=%s cache=%s provider=%s duration_ms=%s"
                % (route, cache, diagnostic["provider"], diagnostic["duration_ms"])
            )
