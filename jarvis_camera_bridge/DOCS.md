# Project Jarvis Camera Bridge

This add-on creates one persistent native go2rtc connection for each **wired**
Google Nest camera, while battery doorbells use a bounded event-driven session
with no polling or preload. It caches JPEGs locally and exposes the same local
stream to Home Assistant live viewers. It does not provide a supported way around Google
Device Access: Google credentials are still required and remain inside this
add-on's private configuration.

## Configuration

1. Reuse the Google Device Access project and OAuth credentials already used by
   the Home Assistant Nest integration.
2. Enter `project_id`, `client_id`, `client_secret`, and `refresh_token`.
3. Set a long random `bridge_token`; the same token is entered when adding the
   **Project Jarvis Camera Bridge** integration. Its default private URL is
   `http://85a88fc0-jarvis-camera-bridge:10500` for this repository.
4. Add each wired camera under `cameras` with a friendly `name` and its SDM
   `device_id`.
5. Add a battery doorbell under `event_cameras` with its friendly `name`, SDM
   `device_id`, and the Home Assistant Nest `event.*` entity that reports a
   chime/ring as `trigger_entity`.
6. Keep `doorbell_session_seconds` between 20 and 60 seconds. The default is 45.
7. Keep port 10500 unexposed unless troubleshooting. Home Assistant reaches the
   add-on over the private Supervisor network.

The default snapshot interval is 15 seconds. The last good image is retained
during an outage and marked stale after 60 seconds. Reconnect attempts use an
exponential cooldown to avoid Google API request storms.

When the configured doorbell event fires, the companion integration opens the
bridge session and emits a local `jarvis_camera_bridge_doorbell` event. An open
Jarvis dashboard displays a temporary live popup and removes it automatically
when the session expires. Spoken and push notifications remain disabled.
