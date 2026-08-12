# Project Jarvis RSS

Fetches up to twenty configured RSS/Atom feeds, sanitizes and deduplicates their
stories, and writes `/share/jarvis_rss/stories.json`. A failed refresh preserves
the last usable cache. Feed content is data only and never authorizes actions.

## Custom feeds

Open the add-on **Configuration** tab and add one or more URLs under
**Custom feeds**. The built-in feeds remain enabled. Duplicate and invalid URLs
are ignored, and the combined list is bounded to twenty feeds. Restarting the
add-on applies the updated list immediately; otherwise it is read again on the
next scheduled refresh.
