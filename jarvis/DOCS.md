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

M21 reflective learning operates only on approved durable memories. Useful
commands include `what have you learned about me`, `what are you uncertain
about`, `show memory connections`, `do not learn from this conversation`, and
`forget everything connected to <subject>`. Reflection never changes Home
Assistant permissions, automations, configuration, or Jarvis code.

M22 proactive assistance can surface low batteries, approved reflective
follow-ups, and temporary repeated-event routine candidates. Useful commands
include `what needs my attention`, `why are you suggesting that`, `not now`,
`never suggest this again`, and `clear pending suggestions`. Suggestions never
execute a device action without an explicit user response. Persistent
notifications respect quiet hours and cooldowns. Proactive voice is disabled
by default and must be enabled both with **Proactive voice enabled** in the
add-on configuration and **Proactive voice output** in the Project Jarvis
Conversation integration options.

M23 adds whole-home situational questions across Home Assistant floors, areas,
groups, device types, and states. Examples include `are any windows upstairs
open`, `which devices in the upstairs office are unavailable`, `what changed
there recently`, and `turn off all lights that are still on upstairs`.
Selections contain only permitted entities, large reads are summarized, and
explicit actions continue through the existing action gateway.

Version 0.13.1 includes the optional complete Jarvis Dashboard System. Download the
`jarvis_ui` folder from the Project Jarvis Home Assistant repository and follow
its `README.md`. Installation remains explicit: the add-on is not granted
write access to Home Assistant's configuration directory. Register
`/local/jarvis/jarvis-ui.js?v=0.13.1` as a JavaScript module in Home Assistant
dashboard resources. The Jarvis cards then appear in the visual card picker.
