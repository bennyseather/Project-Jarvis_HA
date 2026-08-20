"""Local-first SearXNG evidence retrieval and bounded reasoning escalation."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class HybridResearchPolicy:
    searxng_url: str = "http://homeassistant.local:8088/search"
    maximum_results: int = 5
    maximum_pages: int = 3
    maximum_page_bytes: int = 262_144
    timeout_seconds: int = 15
    search_engines: str = "bing"
    normal_model: str = "gpt-5.6-luna"
    escalation_model: str = "gpt-5.6-terra"
    premium_model: str = "gpt-5.6-sol"

    @classmethod
    def from_config(cls, value):
        config = {} if value is None else value
        if not isinstance(config, dict):
            raise ValueError("hybrid_research must be a mapping")
        policy = cls(**{name: config.get(name, getattr(cls(), name))
                        for name in cls.__dataclass_fields__})
        parsed = urlparse(policy.searxng_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("hybrid_research.searxng_url must be HTTP(S)")
        if not 1 <= policy.maximum_results <= 10 or not 0 <= policy.maximum_pages <= 5:
            raise ValueError("hybrid_research result/page bounds are invalid")
        if not 16_384 <= policy.maximum_page_bytes <= 1_048_576:
            raise ValueError("hybrid_research.maximum_page_bytes is invalid")
        if not 3 <= policy.timeout_seconds <= 60:
            raise ValueError("hybrid_research.timeout_seconds is invalid")
        if not re.fullmatch(r"[a-z0-9_-]+(?:,[a-z0-9_-]+)*", policy.search_engines):
            raise ValueError("hybrid_research.search_engines is invalid")
        return policy


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data):
        if not self._ignored and data.strip():
            self.parts.append(data.strip())


class SearXNGResearchClient:
    """Retrieve bounded public evidence; private-network page targets are denied."""

    def __init__(self, policy: HybridResearchPolicy, logger):
        self.policy, self.logger = policy, logger

    def research(self, query):
        candidates = list(self.search_results(query))
        for item in candidates[:self.policy.maximum_pages]:
            try:
                text = self._page_text(item["url"])
                if text:
                    item["content"] = text[:12_000]
            except Exception as exc:
                self.logger.info(f"Research page skipped safely: {exc}")
        return tuple(candidates)

    def search_results(self, query):
        """Return bounded search metadata without fetching result pages."""
        search_url = self.policy.searxng_url + (
            "&" if "?" in self.policy.searxng_url else "?"
        ) + urlencode({
            "q": query,
            "format": "json",
            "language": "auto",
            "engines": self.policy.search_engines,
        })
        try:
            payload = self._json(search_url)
        except Exception as exc:
            self.logger.warning(f"SearXNG search unavailable: {exc}")
            return ()
        candidates, seen = [], set()
        for item in payload.get("results", ()):
            url = str(item.get("url", "")).strip()
            if not url or url in seen or not self._public_url(url):
                continue
            seen.add(url)
            candidates.append({
                "title": str(item.get("title", "")).strip() or url,
                "url": url,
                "snippet": str(item.get("content", "")).strip()[:2000],
            })
            if len(candidates) >= self.policy.maximum_results:
                break
        return tuple(candidates)

    def _json(self, url):
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "Project-Jarvis/0.18"})
        with urlopen(request, timeout=self.policy.timeout_seconds) as response:
            return json.loads(response.read(self.policy.maximum_page_bytes))

    def _page_text(self, url):
        request = Request(url, headers={"Accept": "text/html,text/plain", "User-Agent": "Project-Jarvis/0.18"})
        with urlopen(request, timeout=self.policy.timeout_seconds) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "text/plain"}:
                return ""
            raw = response.read(self.policy.maximum_page_bytes)
            encoding = response.headers.get_content_charset() or "utf-8"
        text = raw.decode(encoding, errors="replace")
        if content_type == "text/plain":
            return " ".join(text.split())
        parser = _TextExtractor()
        parser.feed(text)
        return " ".join(parser.parts)

    @staticmethod
    def _public_url(url):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        try:
            addresses = {
                item[4][0] for item in socket.getaddrinfo(
                    parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
                )
            }
        except OSError:
            return False
        return bool(addresses) and all(
            not (
                ipaddress.ip_address(address).is_private
                or ipaddress.ip_address(address).is_loopback
                or ipaddress.ip_address(address).is_link_local
                or ipaddress.ip_address(address).is_reserved
                or ipaddress.ip_address(address).is_multicast
            )
            for address in addresses
        )


class HybridResearchProvider:
    """Search locally, then use a bounded external reasoning fallback."""

    INSTRUCTIONS = """Answer directly in British English using the supplied evidence.
Distinguish evidence from inference and retain source attribution. If evidence is
insufficient, say so. Never perform Home Assistant actions or infer that a public
profile belongs to the user without disambiguating evidence."""

    def __init__(self, reasoning, search, policy, ledger):
        self.reasoning, self.search, self.policy, self.ledger = reasoning, search, policy, ledger

    def answer(self, query, context, *, force_search=False):
        evidence = self.search.research(query)
        premium = any(phrase in query.casefold() for phrase in (
            "highest quality", "best model", "use premium reasoning",
        ))
        model = self.policy.premium_model if premium else self.policy.normal_model
        local_reasoning = bool(getattr(self.reasoning, "local_first", False))
        if not local_reasoning and not self.ledger.permitted(0.02):
            return {
                "status": "budget_exceeded",
                "message": "The monthly external AI budget has been reached.",
                "sources": tuple({"title": i["title"], "url": i["url"]} for i in evidence),
            }
        evidence_text = "\n\n".join(
            f"[{index}] {item['title']}\nURL: {item['url']}\n"
            f"{item.get('content') or item.get('snippet') or 'No extract available.'}"
            for index, item in enumerate(evidence, 1)
        )
        messages = [{
            "role": "user",
            "content": (
                f"Question: {query}\n\nEvidence:\n{evidence_text or 'No local web evidence was available.'}\n\n"
                f"Jarvis context: {{'memory': {context.get('memory', ())}, "
                f"'knowledge': {context.get('knowledge', ())}}}"
            ),
        }]
        result = self.reasoning.reason(
            instructions=self.INSTRUCTIONS,
            input_messages=messages,
            model=model,
            timeout_seconds=45,
        )
        if (
            result.get("status") != "success"
            and not premium
            and (local_reasoning or self.ledger.permitted(0.05))
        ):
            result = self.reasoning.reason(
                instructions=self.INSTRUCTIONS,
                input_messages=messages,
                model=self.policy.escalation_model,
                timeout_seconds=45,
            )
        sources = tuple({"title": item["title"], "url": item["url"]} for item in evidence)
        result = dict(result)
        result["sources"] = sources
        result["researched"] = bool(sources)
        budget = self.ledger.status()
        if not local_reasoning and budget.get("warning_threshold") is not None:
            result["budget_warning"] = budget
            if result.get("status") == "success":
                percent = round(float(budget["ratio"]) * 100)
                result["message"] = (
                    str(result.get("message", "")).rstrip()
                    + f"\n\nAI budget warning: {percent}% of this month's "
                    "external AI budget has been used."
                )
        return result
