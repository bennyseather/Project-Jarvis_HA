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

M24 adds bounded compound commands such as `turn off the kitchen light and
close the lounge blinds`, `close the blinds, then turn on movie mode`, and
`if the patio door is closed, start the vacuum`. Each step must resolve to a
permitted entity and existing Home Assistant service. Plans are limited to ten
resolved entity actions, use one combined confirmation when required, and
report succeeded, skipped, and failed steps without claiming rollback.

M25 adds explicit household goals. Use `teach goal <name> | <actions>`, then
invoke the goal naturally by name. Use `show goals`, `explain goal <name>`,
`correct goal <name> | <actions>`, and `forget goal <name>` to retain complete
control. `delete <name>` and `delete this goal` are also supported after a goal
has been shown or invoked. Jarvis checks current state and delegates only necessary actions to
M24. Security-related goals always require confirmation.

M26 adds explicit personality controls: `show personality`, `address me as
<name>`, `set personality humour off|subtle`, `set personality formality
relaxed|refined`, `set personality verbosity concise|balanced`, and `reset
personality`. British-English expression and an original subtly synthetic
voice identity never override facts, permissions, confirmations, or safety.

M29 extends that foundation with `set personality warmth
reserved|balanced|warm`, `set personality humour off|subtle|moderate`,
`set personality verbosity concise|balanced|detailed`, `show relationship
preferences`, `forget relationship preferences`, and `explain last response
style`. Voice responses are shorter, preferred names are used sparingly, and
confirmations, failures, safety matters, and sensitive contexts remain
humour-free and structurally unchanged.

M30 adds bounded episodic continuity without retaining raw transcripts.
Automatic low-sensitivity summaries are generated locally and expire after 30
days. Use `remember this conversation`, `pin this conversation`, `what were we
discussing`, `what did we decide about <topic>`, `show recent conversations`,
`forget this conversation`, `forget conversations about <topic>`, and `clear
conversation history`. Sensitive summaries require confirmation. Explicit rich
summaries use Luna and remain subject to the configured monthly AI budget.
The add-on options expose episodic enablement, routine retention days, and the
maximum stored episode count.

M27 adds general OpenAI reasoning and live web research. Jarvis automatically
researches current, niche, uncertain, or explicitly requested topics and
returns bounded source metadata. Use `what sources did you use`, `do not use
web research for this conversation`, and `enable web research for this
conversation` for control. Search findings remain temporary unless you say
`remember this`; `forget this` permanently deletes that approved research
memory. Research never grants Home Assistant or external-action authority.

Version 0.21.0 includes the optional complete Jarvis Dashboard System. Download the
`jarvis_ui` folder from the Project Jarvis Home Assistant repository and follow
its `README.md`. Installation remains explicit: the add-on is not granted
write access to Home Assistant's configuration directory. Register
`/local/jarvis/jarvis-ui.js?v=0.21.0` as a JavaScript module in Home Assistant

## Hybrid research and AI budget

Install and start **Project Jarvis Search**, then keep the default SearXNG URL
or provide another trusted SearXNG JSON endpoint in the Project Jarvis add-on
configuration. The default monthly external-AI budget is USD 10. Ask Jarvis
`show AI usage` or `show AI budget` to inspect the current month. Luna is the
normal reasoning model, Terra is attempted once after a provider failure, and
Sol requires an explicit request for premium reasoning.
dashboard resources. The Jarvis cards then appear in the visual card picker.
