"""Low-latency, source-first intelligence for time-sensitive questions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
import re
import time
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class CurrentInformationPolicy:
    total_timeout_seconds: float = 3.0
    search_timeout_seconds: float = 2.2
    synthesis_timeout_seconds: float = 0.7
    cache_ttl_seconds: int = 300
    maximum_sources: int = 3
    maximum_evidence_characters: int = 4500

    @classmethod
    def from_config(cls, value):
        config = {} if value is None else value
        if not isinstance(config, dict):
            raise ValueError("current_information must be a mapping")
        policy = cls(**{
            name: config.get(name, getattr(cls(), name))
            for name in cls.__dataclass_fields__
        })
        if not 2.0 <= policy.total_timeout_seconds <= 10.0:
            raise ValueError("current_information.total_timeout_seconds is invalid")
        if not 0.5 <= policy.search_timeout_seconds <= policy.total_timeout_seconds:
            raise ValueError("current_information.search_timeout_seconds is invalid")
        if not 0.5 <= policy.synthesis_timeout_seconds <= policy.total_timeout_seconds:
            raise ValueError("current_information.synthesis_timeout_seconds is invalid")
        if not 10 <= policy.cache_ttl_seconds <= 3600:
            raise ValueError("current_information.cache_ttl_seconds is invalid")
        if not 1 <= policy.maximum_sources <= 5:
            raise ValueError("current_information.maximum_sources is invalid")
        if not 1000 <= policy.maximum_evidence_characters <= 12000:
            raise ValueError("current_information.maximum_evidence_characters is invalid")
        return policy


class HomeAssistantReleaseAdapter:
    """Format official Home Assistant release URLs without model synthesis."""

    _URL = re.compile(
        r"^https://www\.home-assistant\.io/blog/(\d{4})/(\d{2})/(\d{2})/release-(\d{4})(\d{1,2})/?$"
    )

    def matches(self, text: str) -> bool:
        normalized = text.casefold()
        return "home assistant" in normalized and "release" in normalized

    def query(self, text: str) -> str:
        return "site:home-assistant.io/blog Home Assistant latest stable release"

    def extract(self, results):
        releases = []
        for item in results:
            match = self._URL.match(str(item.get("url", "")).split("?", 1)[0])
            if match is None:
                continue
            year, month, day, version_year, version_month = map(int, match.groups())
            if (year, month) != (version_year, version_month):
                continue
            releases.append(((version_year, version_month), date(year, month, day), item))
        if not releases:
            return None
        version, published, item = max(releases, key=lambda value: value[:2])
        return {
            "message": (
                f"The latest stable Home Assistant release is {version[0]}.{version[1]}, "
                f"published on {published.day} {published.strftime('%B %Y')}."
            ),
            "sources": ({
                "title": str(item.get("title", "Home Assistant release")),
                "url": str(item["url"]),
            },),
            "adapter": "home_assistant_release",
        }


class AndroidReleaseAdapter:
    """Extract a stable Android release from official Android Developers URLs."""

    _URL = re.compile(
        r"^https://developer\.android\.com/about/versions/(\d+)/(?:blog-release)?/?$"
    )

    def matches(self, text: str) -> bool:
        normalized = text.casefold()
        return "android" in normalized and any(
            word in normalized for word in ("latest", "newest", "current", "release", "version")
        )

    def query(self, text: str) -> str:
        return "site:developer.android.com/about/versions Android latest stable release"

    def extract(self, results):
        releases = []
        for item in results:
            url = str(item.get("url", "")).split("?", 1)[0]
            match = self._URL.match(url)
            if match and "blog-release" in url:
                releases.append((int(match.group(1)), item))
        if not releases:
            return None
        version, item = max(releases, key=lambda value: value[0])
        return {
            "message": f"The latest stable Android release is Android {version}.",
            "sources": ({"title": str(item.get("title", "Android release")), "url": str(item["url"])},),
            "adapter": "android_release",
        }


class PolestarModelAdapter:
    """Extract the newest prominently ranked model from Polestar's official site."""

    _URL = re.compile(r"^https://www\.polestar\.com/[^/]+/polestar-(\d+)/?$")

    def matches(self, text: str) -> bool:
        normalized = text.casefold()
        return "polestar" in normalized and any(
            word in normalized for word in ("latest", "newest", "current", "model", "release")
        )

    def query(self, text: str) -> str:
        return "site:polestar.com/global newest Polestar model"

    def extract(self, results):
        for item in results:
            url = str(item.get("url", "")).split("?", 1)[0]
            match = self._URL.match(url)
            if match:
                model = match.group(1)
                return {
                    "message": f"The newest Polestar model is the Polestar {model}.",
                    "sources": ({"title": str(item.get("title", f"Polestar {model}")), "url": str(item["url"])},),
                    "adapter": "polestar_model",
                }
        return None


class UnitedStatesPresidentAdapter:
    """Extract the current US president from the official White House result."""

    _TITLE = re.compile(r"^President\s+(.+?)\s+[–—-]\s+The White House$", re.IGNORECASE)

    def matches(self, text: str) -> bool:
        normalized = text.casefold()
        return "president" in normalized and any(
            country in normalized for country in ("united states", " u.s.", " us ", "america")
        )

    def query(self, text: str) -> str:
        return "site:whitehouse.gov current President of the United States"

    def extract(self, results):
        for item in results:
            url = str(item.get("url", ""))
            if (urlparse(url).hostname or "").casefold() != "www.whitehouse.gov":
                continue
            match = self._TITLE.match(str(item.get("title", "")).strip())
            if match:
                name = match.group(1).strip()
                return {
                    "message": f"The current president of the United States is {name}.",
                    "sources": ({"title": str(item["title"]), "url": url},),
                    "adapter": "us_president",
                }
        return None


class CurrentInformationIntelligence:
    """Search first and answer from bounded, preferentially primary evidence."""

    _TEMPORAL = re.compile(
        r"\b(latest|newest|current(?:ly)?|today|tonight|recent|recently|released?|"
        r"version|price|cost|schedule|score|standings|office[- ]holder|president|"
        r"prime minister|ceo|chief executive|model|exchange rate|stock price)\b",
        re.IGNORECASE,
    )
    _EXPLICIT = re.compile(
        r"\b(search|research|look up|web search|browse|verify online)\b", re.IGNORECASE
    )
    _LOCAL_HOME = re.compile(
        r"\b(living room|bedroom|kitchen|bathroom|garage|home|house|here|"
        r"temperature|humidity|light|lights|lock|door|window|thermostat|sensor|"
        r"camera|vacuum|mower|washing machine)\b",
        re.IGNORECASE,
    )
    _OFFICIAL_HINTS = (
        "official", "government", "documentation", "release notes", "newsroom",
    )
    _LOW_AUTHORITY = (
        "wikipedia.org", "reddit.com", "facebook.com", "x.com", "youtube.com",
        "pinterest.", "quora.com",
    )

    def __init__(self, search, reasoning, policy=None, logger=None, clock=time.monotonic):
        self.search = search
        self.reasoning = reasoning
        self.policy = policy or CurrentInformationPolicy()
        self.logger = logger
        self.clock = clock
        self.adapters = (
            HomeAssistantReleaseAdapter(),
            AndroidReleaseAdapter(),
            PolestarModelAdapter(),
            UnitedStatesPresidentAdapter(),
        )
        self._cache = {}

    def is_current_question(self, text: str) -> bool:
        normalized = " ".join(str(text).casefold().strip(" .?!").split())
        if not normalized:
            return False
        specialised_public_question = (
            "home assistant" in normalized and "release" in normalized
        )
        if self._LOCAL_HOME.search(normalized) and not specialised_public_question:
            return False
        return bool(self._TEMPORAL.search(normalized) or self._EXPLICIT.search(normalized))

    async def handle(self, text: str, *, voice_mode=False):
        if not self.is_current_question(text):
            return None
        key = " ".join(text.casefold().strip(" .?!").split())
        cached = self._cache.get(key)
        now = self.clock()
        if cached and now - cached[0] <= self.policy.cache_ttl_seconds:
            result = dict(cached[1])
            result["cache"] = "hit"
            result["timings"] = {"total_ms": 0}
            return result
        started = now
        try:
            result = await asyncio.wait_for(
                self._resolve(text, voice_mode=voice_mode, started=started),
                timeout=self.policy.total_timeout_seconds,
            )
        except asyncio.TimeoutError:
            result = self._fallback("deadline", started)
        result.setdefault("cache", "miss")
        if result.get("status") == "success" and not result.get("fallback_reason"):
            self._cache[key] = (self.clock(), dict(result))
        return result

    async def _resolve(self, text, *, voice_mode, started):
        adapter = next((item for item in self.adapters if item.matches(text)), None)
        query = adapter.query(text) if adapter else text[:300]
        search_started = self.clock()
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(self.search.search_results, query),
                timeout=self.policy.search_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return self._fallback("search_timeout", started)
        ranked = self._rank(raw, query)[: self.policy.maximum_sources]
        search_ms = round((self.clock() - search_started) * 1000)
        if adapter:
            extracted = adapter.extract(ranked)
            if extracted:
                return self._success(extracted, started, search_ms, synthesis_ms=0)
        if not ranked:
            return self._fallback("no_authoritative_evidence", started)
        synthesis_started = self.clock()
        result = await self._synthesise(text, ranked, voice_mode)
        synthesis_ms = round((self.clock() - synthesis_started) * 1000)
        if result.get("status") != "success" or not str(result.get("message", "")).strip():
            return self._fallback("synthesis_unavailable", started, ranked)
        return self._success({
            "message": str(result["message"]).strip(),
            "sources": tuple({"title": item["title"], "url": item["url"]} for item in ranked),
            "adapter": "bounded_local_synthesis",
        }, started, search_ms, synthesis_ms)

    async def _synthesise(self, question, evidence, voice_mode):
        evidence_text = "\n".join(
            f"[{index}] {item['title']} | {item['url']} | {item.get('snippet', '')}"
            for index, item in enumerate(evidence, 1)
        )[: self.policy.maximum_evidence_characters]
        request = {
            "instructions": (
                "Answer only from the verified source metadata supplied. Use one or two "
                "short British-English sentences and no Markdown or URLs. Prefer the "
                "highest-ranked official source. If the evidence does not establish the "
                "answer, say that current information could not be verified."
            ),
            "input_messages": [{
                "role": "user",
                "content": f"Question: {question[:300]}\nEvidence:\n{evidence_text}",
            }],
            "timeout_seconds": self.policy.synthesis_timeout_seconds,
        }
        local_reason = getattr(self.reasoning, "reason_local", None)
        if local_reason is None:
            return {"status": "unavailable", "message": ""}
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(local_reason, **request),
                timeout=self.policy.synthesis_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return {"status": "timeout", "message": ""}

    def _rank(self, results, query):
        query_words = set(re.findall(r"[a-z0-9]+", query.casefold()))
        ranked = []
        for item in results or ():
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip() or url
            if not url:
                continue
            host = (urlparse(url).hostname or "").casefold()
            haystack = f"{title} {item.get('snippet', '')}".casefold()
            relevance = len(query_words & set(re.findall(r"[a-z0-9]+", haystack)))
            authority = 0
            if host.endswith(".gov") or ".gov." in host or host.endswith(".government.no"):
                authority += 100
            if any(hint in haystack for hint in self._OFFICIAL_HINTS):
                authority += 35
            host_words = set(re.findall(r"[a-z0-9]+", host))
            if query_words & host_words:
                authority += 45
            if any(part in host for part in self._LOW_AUTHORITY):
                authority -= 100
            authority += min(relevance * 4, 32)
            value = dict(item)
            value["title"], value["url"] = title, url
            value["authority_score"] = authority
            ranked.append(value)
        return tuple(sorted(ranked, key=lambda item: item["authority_score"], reverse=True))

    def _success(self, extracted, started, search_ms, synthesis_ms):
        result = {
            "status": "success",
            "message": extracted["message"],
            "sources": extracted["sources"],
            "researched": True,
            "provider": "current_information",
            "adapter": extracted["adapter"],
            "timings": {
                "search_ms": search_ms,
                "synthesis_ms": synthesis_ms,
                "total_ms": round((self.clock() - started) * 1000),
            },
        }
        if self.logger:
            self.logger.info(
                "Current information resolved via %s in %sms (search=%sms, synthesis=%sms)",
                extracted["adapter"],
                result["timings"]["total_ms"],
                search_ms,
                synthesis_ms,
            )
        return result

    def _fallback(self, reason, started, evidence=()):
        if self.logger:
            self.logger.warning(f"Current information fallback: {reason}")
        return {
            "status": "success",
            "message": "I couldn't verify that current information quickly enough. Please try again shortly.",
            "sources": tuple(
                {"title": item["title"], "url": item["url"]}
                for item in evidence[: self.policy.maximum_sources]
            ),
            "researched": bool(evidence),
            "provider": "current_information",
            "fallback_reason": reason,
            "timings": {"total_ms": round((self.clock() - started) * 1000)},
        }
