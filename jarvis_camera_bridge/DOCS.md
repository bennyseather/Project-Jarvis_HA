# Project Jarvis Camera Bridge

This add-on creates one persistent native go2rtc connection for each **wired**
Google Nest camera, caches a JPEG locally, and exposes the same local stream to
Home Assistant live viewers. It does not provide a supported way around Google
Device Access: Google credentials are still required and remain inside this
add-on's private configuration.

## Configuration

1. Reuse the Google Device Access project and OAuth credentials already used by
   the Home Assistant Nest integration.
2. Enter `project_id`, `client_id`, `client_secret`, and `refresh_token`.
3. Set a long random `bridge_token`; the same token is entered when adding the
   **Project Jarvis Camera Bridge** integration. Its default private URL is
   `http://85a88fc0-jarvis-camera-bridge:10500` for this repository.
4. Add each wired camera with a friendly `name` and its SDM `device_id`.
5. Keep port 10500 unexposed unless troubleshooting. Home Assistant reaches the
   add-on over the private Supervisor network.

The default snapshot interval is 15 seconds. The last good image is retained
during an outage and marked stale after 60 seconds. Reconnect attempts use an
exponential cooldown to avoid Google API request storms.

Doorbell events are recorded by the companion integration, but this release
deliberately performs no spoken or push notification.
