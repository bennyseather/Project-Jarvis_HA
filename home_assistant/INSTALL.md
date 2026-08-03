# Installing Project Jarvis on Home Assistant OS

1. In Home Assistant, open **Settings → Add-ons → Add-on Store → Repositories**
   and add `https://github.com/bennyseather/Project-Jarvis_HA`.
2. Install and start **Project Jarvis Search**. Its default endpoint is
   `http://homeassistant.local:8088/search`.
3. Install **Project Jarvis**, configure the OpenAI and bridge API keys, the
   SearXNG endpoint, and the monthly external-AI budget, then start it.
4. Copy `home_assistant/custom_components/jarvis_conversation` to
   `/config/custom_components/jarvis_conversation`, then restart Home Assistant.
5. Open **Settings → Devices & services → Add integration**, choose
   **Project Jarvis Conversation**, enter `http://local-jarvis:8099` and the
   same bridge API key.
6. Select Project Jarvis as the conversation agent in Assist, then test a
   harmless request for an entity you choose.
7. To configure external voice output, open the Project Jarvis Conversation
   integration's **Configure** dialog. Select the microphone device, speaker or
   speaker group, and TTS provider, then enable external voice output.
8. Review the add-on's proactive configuration. Persistent notifications are
   enabled by default, quiet hours are 22:00–07:00, and proactive voice is
   disabled. Enable proactive voice in both the add-on and conversation
   integration only if you explicitly want it.

Do not expose ports 8099 or 8088 to the internet. They are intended for the
trusted Home Assistant network only.

Upgrading through the add-on repository preserves existing memory. Version
0.22.1 adds corrected local Piper voice refinement discovery. No reset
or reinstallation is required.

For the optional local British synthetic voice, install the official Piper app
first and then install **Project Jarvis Voice**. Its instructions are in
`jarvis_voice/DOCS.md`.

The optional Jarvis UI Design System is published in the release repository's
`jarvis_ui` folder. Follow its `README.md` for manual theme, background, card,
icon, and example-dashboard installation. The add-ons do not write these
files to Home Assistant's `/config` directory.
