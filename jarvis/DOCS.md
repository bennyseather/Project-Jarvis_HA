# Project Jarvis add-on

Set an OpenAI API key and a long random bridge API key in the add-on options.
The add-on stores its SQLite database in its persistent add-on configuration
folder. It uses the Home Assistant Supervisor's internal API proxy and does not
need a Home Assistant long-lived token.

Jarvis controls discovered device entities immediately. Home Assistant
administration, backups, add-on management, configuration changes, automations,
and scripts are intentionally unavailable. Use `home exclude <entity_id>` and
restart the add-on to remove a device from Jarvis access.

Install the companion `jarvis_conversation` custom component, then configure
its bridge URL as `http://local-jarvis:8099` for a locally installed add-on and
enter the same bridge API key.

To enable M20 voice output, open **Settings -> Devices & services**, select
**Project Jarvis Conversation**, and choose **Configure**. Enable external voice
output, select the microphone device, media player or speaker group, and TTS
provider. Requests from other devices and typed Assist are not routed to the
external speaker.
