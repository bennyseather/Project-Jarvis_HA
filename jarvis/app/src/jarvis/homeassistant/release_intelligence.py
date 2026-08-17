"""Fast authoritative Home Assistant release lookup."""

from __future__ import annotations

import asyncio
from datetime import date
import re


class HomeAssistantReleaseIntelligence:
    """Resolve the latest official release without language-model synthesis."""

    _URL = re.compile(
        r"^https://www\.home-assistant\.io/blog/(\d{4})/(\d{2})/(\d{2})/release-(\d{4})(\d{1,2})/?$"
    )

    def __init__(self, search) -> None:
        self._search = search

    async def handle(self, text: str):
        normalized = " ".join(text.casefold().strip(" .?!").split())
        if not (
            "home assistant" in normalized
            and "release" in normalized
            and any(word in normalized for word in ("latest", "stable", "newest"))
        ):
            return None
        results = await asyncio.to_thread(
            self._search.search_results,
            "site:home-assistant.io/blog Home Assistant latest release",
        )
        releases = []
        for item in results:
            match = self._URL.match(str(item.get("url", "")).split("?", 1)[0])
            if match is None:
                continue
            year, month, day, version_year, version_month = map(int, match.groups())
            if year != version_year or month != version_month:
                continue
            releases.append(((version_year, version_month), date(year, month, day), item))
        if not releases:
            return None
        version, published, item = max(releases, key=lambda value: value[:2])
        return {
            "status": "success",
            "message": (
                f"The latest stable Home Assistant release is {version[0]}.{version[1]}, "
                f"published on {published.day} {published.strftime('%B %Y')}."
            ),
            "sources": ({"title": str(item.get("title", "Home Assistant release")), "url": item["url"]},),
            "researched": True,
        }
