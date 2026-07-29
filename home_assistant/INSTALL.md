# Installing Project Jarvis on Home Assistant OS

1. Create a private add-on repository containing the *contents* of this
   project's `home_assistant/addons` folder at its root. Replace the placeholder
   URL in that repository's `repository.yaml` with its own repository URL.
2. In Home Assistant, open **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
   and add the repository URL. Install **Project Jarvis** from the new
   repository, set an OpenAI API key and a long random bridge API key, then
   start it.
3. Copy `home_assistant/custom_components/jarvis_conversation` to
   `/config/custom_components/jarvis_conversation` in Home Assistant, then
   restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**, choose **Project
   Jarvis Conversation**, enter `http://local-jarvis:8099` and the same bridge
   API key.
5. Select Project Jarvis as the conversation agent in Assist, then test a
   harmless request for an entity you choose.
6. To configure external voice output, open the Project Jarvis Conversation
   integration's **Configure** dialog. Select the microphone device, speaker or
   speaker group, and TTS provider, then enable external voice output.
7. Review the add-on's `proactive` configuration. Persistent notifications are
   enabled by default, quiet hours are 22:00–07:00, and proactive voice is
   disabled. Enable proactive voice in both the add-on configuration and the
   conversation integration only if you explicitly want it.

Do not expose port 8099 to the internet. The add-on is intended to be reached
only through the internal Home Assistant network.

After upgrading to version 0.11.0, existing memory is preserved automatically.
No reset or reinstallation is required.

The optional Jarvis UI Design System is published in the release repository's
`jarvis_ui` folder. Follow its `README.md` to install the squared HUD theme,
backgrounds, visually editable cards, `jarvis:` icons, and example dashboards.
The add-on intentionally does not write to Home Assistant's `/config`
directory.
