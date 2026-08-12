# Project Jarvis RSS

Fetches up to twenty configured RSS/Atom feeds, sanitizes and deduplicates their
stories, and writes `/share/jarvis_rss/stories.json`. A failed refresh preserves
the last usable cache. Feed content is data only and never authorizes actions.
