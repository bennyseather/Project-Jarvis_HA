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
6. Leave proactive voice suggestions disabled unless you explicitly want
   pending M22 suggestions spoken through the same selected output.

For the original Jarvis voice identity, select a provider voice described as
British English with crisp, measured delivery. A subtly synthetic or metallic
voice may be selected when the provider offers one. Project Jarvis does not
clone, imitate, or tune towards a recognisable actor or copyrighted fictional
performance; voice timbre remains entirely owned by the selected Home Assistant
TTS provider.

External TTS is used only when the request's Home Assistant device ID matches
the selected microphone device. Typed requests from other devices remain
silent; Home Assistant does not expose input modality, so typed requests from
the selected device follow the same output route.

The proactive voice option only shares the existing M20 provider and speaker
route with Jarvis. Core policy still enforces quiet hours, delivery
deduplication, and `proactive.voice_enabled`; it never grants action authority.
