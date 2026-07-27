# Project Jarvis Conversation integration

Install this custom component after the Jarvis add-on is running. Configure its
local bridge URL and add-on API key through the Home Assistant integration UI.
It is intentionally a thin proxy: authorization and confirmation stay in
Jarvis.

For external voice output, open the integration's **Configure** dialog and:

1. Enable external voice output.
2. Select the Home Assistant device providing the microphone.
3. Select the media player or speaker group for Jarvis replies.
4. Select a TTS provider and language.
5. Keep local-audio suppression enabled to prevent duplicate speech.

External TTS is used only when the request's Home Assistant device ID matches
the selected microphone device. Typed requests from other devices remain
silent; Home Assistant does not expose input modality, so typed requests from
the selected device follow the same output route.
