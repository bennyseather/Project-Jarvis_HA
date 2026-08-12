"""Bounded RSS/Atom fetcher that publishes a normalized local cache."""
from __future__ import annotations

import hashlib
import html
import json
import logging
from pathlib import Path
import re
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import feedparser

LOG = logging.getLogger("jarvis_rss")
OPTIONS = Path("/data/options.json")
CACHE = Path("/share/jarvis_rss/stories.json")
TAG = re.compile(r"<[^>]+>")
MAXIMUM_FEEDS = 20


def clean(value, maximum=800):
    return " ".join(html.unescape(TAG.sub(" ", str(value or ""))).split())[:maximum]


def fetch(url, timeout=20):
    request = Request(url, headers={"User-Agent": "Project-Jarvis-RSS/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return response.read(2_000_000)


def normalize(url, payload):
    parsed = feedparser.parse(payload)
    source = clean(parsed.feed.get("title")) or urlparse(url).netloc
    stories = []
    for entry in parsed.entries:
        link = str(entry.get("link", ""))[:1500]
        title = clean(entry.get("title"), 300)
        if not title or not link.startswith(("http://", "https://")):
            continue
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", published) if published else ""
        media = entry.get("media_content") or entry.get("media_thumbnail") or ()
        image = str(media[0].get("url", ""))[:1500] if media else ""
        identity = hashlib.sha256((link or source + title).encode("utf-8")).hexdigest()[:20]
        stories.append({
            "id": identity, "source": source, "title": title,
            "summary": clean(entry.get("summary") or entry.get("description")),
            "url": link, "image": image, "published": timestamp,
            "category": clean((entry.get("tags") or [{}])[0].get("term", ""), 80),
        })
    return source, stories


def configured_feeds(options):
    """Merge built-in and custom feeds, preserving order and removing duplicates."""
    values = list(options.get("feeds") or ()) + list(options.get("custom_feeds") or ())
    feeds = []
    seen = set()
    for value in values:
        url = str(value).strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or url in seen:
            continue
        seen.add(url)
        feeds.append(url)
        if len(feeds) == MAXIMUM_FEEDS:
            break
    return feeds


def refresh(options):
    previous = {}
    try:
        previous = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    merged, health = {}, []
    for url in configured_feeds(options):
        try:
            source, stories = normalize(url, fetch(url, options["request_timeout_seconds"]))
            health.append({"url": url, "source": source, "status": "ok", "stories": len(stories)})
            for story in stories:
                merged[story["id"]] = story
        except Exception as error:
            LOG.warning("Feed failed %s: %s", url, error)
            health.append({"url": url, "source": urlparse(url).netloc, "status": "error", "error": str(error)[:160]})
    if not merged:
        for story in previous.get("stories", []):
            merged[story.get("id", "")] = story
    stories = sorted(merged.values(), key=lambda item: item.get("published", ""), reverse=True)[:options["maximum_stories"]]
    payload = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stories": stories, "feeds": health}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(CACHE)
    LOG.info("Cached %d unique stories from %d feeds", len(stories), len(health))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    while True:
        options = json.loads(OPTIONS.read_text(encoding="utf-8"))
        options.setdefault("feeds", [])
        options.setdefault("custom_feeds", [])
        options.setdefault("refresh_minutes", 15)
        options.setdefault("maximum_stories", 100)
        options.setdefault("request_timeout_seconds", 20)
        refresh(options)
        time.sleep(max(300, int(options["refresh_minutes"]) * 60))


if __name__ == "__main__":
    main()
