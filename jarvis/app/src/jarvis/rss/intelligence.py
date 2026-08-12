"""Read-only, cache-backed RSS intelligence."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class RSSPolicy:
    enabled: bool = True
    cache_path: str = "/share/jarvis_rss/stories.json"
    maximum_spoken_stories: int = 5

    @classmethod
    def from_config(cls, value):
        value = value or {}
        if not isinstance(value, dict): raise ValueError("rss must be a mapping")
        enabled = value.get("enabled", True)
        limit = value.get("maximum_spoken_stories", 5)
        path = value.get("cache_path", cls.cache_path)
        if not isinstance(enabled, bool): raise ValueError("rss.enabled must be a boolean")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10: raise ValueError("rss.maximum_spoken_stories must be between 1 and 10")
        if not isinstance(path, str) or not path: raise ValueError("rss.cache_path must be a non-empty string")
        return cls(enabled, path, limit)


class RSSIntelligence:
    def __init__(self, policy: RSSPolicy): self.policy = policy; self._selection = {}

    def handle(self, text, conversation_id, *, voice_mode=False):
        normalized = " ".join(text.casefold().strip(" .?!").split())
        if not self.policy.enabled: return None
        followup = re.fullmatch(r"(?:tell me more about|more on|open) (?:the )?(?:story )?(?:number )?(\d+|first|second|third|fourth|fifth)", normalized)
        relevant = any(phrase in normalized for phrase in ("top stories", "latest news", "news headlines", "rss", "technology news", "news from", "happening in norway"))
        if not relevant and not followup: return None
        data = self._load()
        stories = list(data.get("stories", ()))
        if followup:
            chosen = self._selection.get(conversation_id, ())
            indexes = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
            index = indexes.get(followup.group(1), int(followup.group(1)) if followup.group(1).isdigit() else 1) - 1
            if not 0 <= index < len(chosen): return {"status": "clarification_required", "message": "Please choose one of the listed stories."}
            story = chosen[index]
            message = f"{story.get('title')}. {story.get('summary') or 'No feed summary is available.'} Source: {story.get('source')}."
            return {"status": "success", "message": message, "url": story.get("url"), "source": story.get("source")}
        if "norway" in normalized: stories = [item for item in stories if "nrk" in item.get("source", "").casefold() or "norway" in (item.get("category", "") + item.get("summary", "")).casefold()]
        elif "technology" in normalized: stories = [item for item in stories if any(word in (item.get("category", "") + item.get("title", "") + item.get("summary", "")).casefold() for word in ("tech", "ai", "software", "computer"))]
        source = re.search(r"news from (.+)$", normalized)
        if source: stories = [item for item in stories if source.group(1) in item.get("source", "").casefold()]
        limit = self.policy.maximum_spoken_stories if voice_mode else min(10, self.policy.maximum_spoken_stories + 3)
        chosen = tuple(stories[:limit]); self._selection[conversation_id] = chosen
        if not chosen: return {"status": "unavailable", "message": "No matching RSS stories are available in the current cache."}
        message = "Top stories: " + " ".join(f"{index}. {item.get('title')}." for index, item in enumerate(chosen, 1))
        return {
            "status": "success",
            "message": message,
            "stories": chosen,
            "preserve_voice_list": True,
        }

    def _load(self):
        try:
            value = json.loads(Path(self.policy.cache_path).read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError): return {}
