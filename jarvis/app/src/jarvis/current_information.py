"""Low-latency, source-first intelligence for time-sensitive questions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
import json
import re
import time
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_official_document(url, timeout):
    """Fetch one bounded document from an adapter-owned official endpoint."""

    is_android_probe = (
        url.startswith("https://developer.android.com/about/versions/")
        and url.endswith("/blog-release")
    )
    request = Request(
        url,
        headers={
            "Accept": "application/json,text/html,text/plain",
            "User-Agent": "Project-Jarvis/0.45",
        },
        method="HEAD" if is_android_probe else "GET",
    )
    try:
        opener = build_opener(_NoRedirect()) if is_android_probe else None
        response = (
            opener.open(request, timeout=timeout)
            if opener else urlopen(request, timeout=timeout)
        )
        with response:
            content = response.read(262_144).decode("utf-8", errors="replace")
            return {"url": url, "resolved_url": response.geturl(), "content": content}
    except HTTPError as exc:
        if is_android_probe and 300 <= exc.code < 400:
            return {
                "url": url,
                "resolved_url": exc.headers.get("Location", url),
                "content": "",
            }
        raise


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

    def direct_urls(self):
        return ("https://api.github.com/repos/home-assistant/core/releases/latest",)

    def extract_direct(self, documents):
        for item in documents:
            try:
                tag = str(json.loads(item["content"]).get("tag_name", ""))
            except (ValueError, TypeError):
                continue
            if re.fullmatch(r"\d{4}\.\d+\.\d+", tag):
                return {
                    "message": f"The latest stable Home Assistant release is {tag}.",
                    "sources": ({"title": "Home Assistant Core releases", "url": item["url"]},),
                    "adapter": "home_assistant_release",
                }
        return None

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

    def direct_urls(self):
        expected = date.today().year - 2009
        return tuple(
            f"https://developer.android.com/about/versions/{version}/blog-release"
            for version in range(expected - 1, expected + 2)
        )

    def extract_direct(self, documents):
        releases = []
        for item in documents:
            match = self._URL.match(item["url"])
            if match and "blog-release" in item["url"]:
                releases.append((int(match.group(1)), item))
        if not releases:
            return None
        version, item = max(releases, key=lambda value: value[0])
        return {
            "message": f"The latest stable Android release is Android {version}.",
            "sources": ({"title": f"Android {version} release", "url": item["url"]},),
            "adapter": "android_release",
        }

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

    def direct_urls(self):
        return ("https://www.polestar.com/no/",)

    def extract_direct(self, documents):
        models = [
            int(value)
            for item in documents
            for value in re.findall(
                r"\bPolestar\s+([1-9]\d?)\b", item["content"], re.IGNORECASE
            )
        ]
        if not models:
            return None
        model = max(models)
        return {
            "message": f"The newest Polestar model is the Polestar {model}.",
            "sources": ({"title": "Polestar models", "url": documents[0]["url"]},),
            "adapter": "polestar_model",
        }

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

    def direct_urls(self):
        return ("https://www.whitehouse.gov/administration/",)

    def extract_direct(self, documents):
        for item in documents:
            match = re.search(
                r"President\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3})",
                item["content"],
            )
            if match:
                name = match.group(1).strip()
                return {
                    "message": f"The current president of the United States is {name}.",
                    "sources": ({"title": "The White House administration", "url": item["url"]},),
                    "adapter": "us_president",
                }
        return None

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

    def __init__(
        self,
        search,
        reasoning,
        policy=None,
        logger=None,
        clock=time.monotonic,
        official_fetcher=None,
    ):
        self.search = search
        self.reasoning = reasoning
        self.policy = policy or CurrentInformationPolicy()
        self.logger = logger
        self.clock = clock
        self.official_fetcher = official_fetcher
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
        search_task = asyncio.create_task(
            asyncio.to_thread(self.search.search_results, query)
        )
        direct_task = (
            asyncio.create_task(self._direct_documents(adapter))
            if adapter and self.official_fetcher is not None
            else None
        )
        search_timed_out = False
        try:
            raw = await asyncio.wait_for(
                search_task, timeout=self.policy.search_timeout_seconds
            )
        except asyncio.TimeoutError:
            raw = ()
            search_timed_out = True
        ranked = self._rank(raw, query)[: self.policy.maximum_sources]
        search_ms = round((self.clock() - search_started) * 1000)
        if adapter:
            extracted = adapter.extract(ranked)
            if extracted:
                if direct_task:
                    direct_task.cancel()
                return self._success(extracted, started, search_ms, synthesis_ms=0)
            if direct_task:
                direct = await direct_task
                extracted = adapter.extract_direct(direct) if direct else None
                if extracted:
                    return self._success(
                        extracted,
                        started,
                        round((self.clock() - search_started) * 1000),
                        synthesis_ms=0,
                    )
        if not ranked:
            reason = "search_timeout" if search_timed_out else "no_authoritative_evidence"
            return self._fallback(reason, started)
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

    async def _direct_documents(self, adapter):
        tasks = [
            asyncio.to_thread(self._fetch_official, url)
            for url in adapter.direct_urls()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return tuple(item for item in results if isinstance(item, dict))

    def _fetch_official(self, url):
        return self.official_fetcher(url, self.policy.search_timeout_seconds)

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
                f"Current information resolved via {extracted['adapter']} in "
                f"{result['timings']['total_ms']}ms (search={search_ms}ms, "
                f"synthesis={synthesis_ms}ms)"
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
