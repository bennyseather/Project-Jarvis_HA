# Project Jarvis add-on

## Connected reply repair (0.45.66)

Future-date follow-ups change plans and forecasts, not when sensors were observed.
A recorded calendar clash is a reason to check which commitments apply, not proof
that someone must stay home. Local-weather questions use the supplied forecast
and a recorded appointment where available, with conditional advice if going out;
they do not assume the event is indoors/outdoors or discuss unrelated destinations.
Missing calendars/readings stay unknown. An unchanged coverage warning need not
repeat on a scoped follow-up, but readings are fetched again and remain partial.
This is a bounded local interpretation, not a universal semantic guarantee.
Saved voice is preserved; real audio/accent and reminder acceptance remain held.

## Connected understanding (0.45.65)

Use a named person, a matched speaker, or the household for practical connected
questions, such as:

- “What should we sort out before leaving tomorrow?” followed by “And Friday?”
- “How will the weather affect Mia's plans tomorrow?”
- “What should Benny prepare for the next trip, and what is open at home?”
- “How does the weather affect things at home today, and check the latest Home Assistant release?”

Qwen explains fresh permitted facts, rather than issuing tools. Home checks cover
exposed individual door/window contacts, lights, locks and covers only. Current HA
reports do not establish future departure state, physical verification or safety;
recheck relevant issues nearer departure. Unavailable readings and unconnected
personal calendars remain unknown. A home forecast is never destination weather.
Flight times are not leave-home times, and household routines are not attendance.

An explicit public lookup uses only the literal lookup clause, never household
context or source results as a search query. Personal/household identifiers in
that clause are rejected; research-disable settings are respected. Source links
remain in text. Public lookups are not automatically repeated on date follow-ups.
Ambiguous references clarify. Next-trip and supported known-destination selectors
reuse the existing travel adapter; unsupported selectors ask for a narrower query.

Connected output is buffered and checked, with at most one correction and a total
16-second bound. Simple facts/controls keep existing fast paths.
If departure wording is rejected and no appointments are in the evidence, a
verified home-state recheck can be returned with an explicit incomplete-planning
notice. This is a partial code-calculated recovery, not an accepted model draft.
It cannot suppress a recorded appointment, travel selection or public lookup.
No device,
calendar, recording or reminder is created. Your saved voice and STT/TTS settings
are unchanged. This release does not resume deferred audio/accent or real-reminder
human acceptance, and finite tests cannot guarantee every paraphrase is understood.

## Calendar understanding (0.45.61)

Ask about preparation, a person's day/week, which day looks busiest, appointment
conflicts or fitting an activity into a time window. A matched speaker resolves
"my"; named household questions still use shared knowledge. Date follow-ups keep
the person and purpose. After a duration clarification, "About 30 minutes" stays
in the same calendar conversation.

Jarvis calculates timing relationships, calendar load, overlaps and possible
calendar-only gaps, then uses the local model for a concise connected explanation.
Model output is buffered and checked, with at most one correction. A verified
calculation-based answer may replace an unsafe model draft; this is not evidence
of frontier-model general intelligence or perfect semantic accuracy.

Usual routines do not prove attendance. Missing/empty calendars do not prove
availability. Simultaneous events for different people may require coordination,
but do not assign transport or childcare. No calendar events are changed by these
questions. No speaker enrolment, microphone, STT/TTS or voice-worker change is
needed. Existing action confirmations and non-calendar inference defaults remain.
This update does not resume the separately deferred accent/reminder human tests.

Set a long random bridge API key in the add-on options. An OpenAI API key is
optional: leave it empty and disable OpenAI fallback for local-only operation.
An empty key never falls back to a development computer's environment key.

## Household personalisation (0.45.59)

With an approved household profile and shared conversational updates enabled,
try `Give me my briefing today`, `What does my day look like tomorrow?`,
`What's next for me?`, `Give us a household briefing for next week`, followed by
`And the following week?` or `Tell me more` in the same conversation.

Current voice relevance selects whose "my" to use; an unknown speaker is asked
to name a person. Voice does not grant administrator authority, prove presence
or enrol other people. Named household information remains shared. The existing
family calendar is attributed to its configured person; connected work/travel
calendars are not treated as every household member's personal calendar.
Briefings distinguish recorded routines, planned appointments, empty responses
and unavailable sources. Overlap notices do not modify appointments or assign
a child's activity to a parent. Dates/times use Europe/Oslo.

Ask `What do you remember about me?` or `Show household notes` to review saved
information. `Remember I prefer concise answers` uses a current voice match;
otherwise use an explicit name. Review the proposal and say `confirm household
change` or `yes` in that same conversation. A later unrelated question clears
the pending proposal. Nothing is saved just because Jarvis understood a statement.

For example, after saving `Mia likes painting`, say `Change "Mia likes painting"
to "Mia likes drawing"` or `Forget "Mia likes painting"`. Quote an existing note
exactly, or use its displayed ID. Confirm each proposed change. `Cancel household
change` discards it; `Undo last household change` proposes a confirmed reversal.
Removal retains protected undo history and is not secure erasure. Notes never
change structured schedules, alarms, devices or permissions by themselves.

Confirmed concise/detailed answer preferences affect the new briefings and local
model presentation only. Whole relevant notes are selected with a bounded context;
the full saved list stays on the household information page. Passwords and API
keys must not be stored as conversational notes.

For bridge-key maintenance, change the add-on credential and use the integration's
supported Reconfigure flow to validate the replacement against its existing URL.
The flow preserves voice-routing options. Old backups may contain old credentials:
do not undo a security rotation by restoring those options. Disabling/removing
an OpenAI key locally does not revoke that key in the OpenAI account.

## Planning, preparation and understanding (0.45.60)

Ask `What should I prepare for tomorrow?`, `Help us plan next week`, or
`What should Mia prepare for tomorrow?`. Follow with `And Friday?` or `And the
following week?` in the same speaker's conversation. These are on-demand reads,
not autonomous planning or household actions. Home-area weather is matched to
the requested dates, not assumed to be destination weather. Missing forecast
coverage, calendar outages and recorded routines remain explicit. No travel
time from home is invented. `Help me prepare for my next trip` reuses Benny's
approved travel source; other people do not inherit his travel calendar.

Use `Remind me to check my bag tomorrow at 08:00` or `Remind Mia tomorrow at
08:00 to check her bag`. Review the owner, task, precise Norway time and delivery
channel, then reply `yes` or `confirm reminder`; `no` discards the proposal.
`In 20 minutes` works too. Ambiguous am/pm, past times and DST fold/gap clock
times require clarification. A voice match supplies relevance, not authority.
Named reminders remain shared like the household's other knowledge.

`Show my reminders`, `Show Mia's reminders`, and `Show all reminders` show the
saved task, time, state and ID. `Move my reminder to check my bag to tomorrow at
09:00` and `Cancel my reminder to check my bag` propose a change only if that
exact task selects one reminder. Otherwise use `Reschedule reminder <id> to
tomorrow at 09:00`, `Cancel reminder <id>` or `Complete reminder <id>`.
Every mutation requires confirmation. Unrelated questions, changed speakers,
expiry or concurrent changes invalidate pending confirmation. Calendar
appointments are separate and never edited by these commands.

Confirmed reminders are stored in `personal_reminders.json` next to the profile
in addon_config. Briefings/preparation can include them. Delivery creates a
Home Assistant persistent notification within roughly 30 seconds while the
add-on/HA are healthy. It is NOT spoken audio, push-to-phone or an alarm clock.
Three failed delivery attempts leave a visible failed state; reschedule to
retry. After more than seven days of downtime a due reminder becomes missed,
not a burst of old announcements. A stable notification ID prevents duplicate
notification cards on uncertain retries; it does not prove a person read one.
Cancellation/completion never removes a notification already displayed. Do not
depend on this feature for safety-critical wakeups. Capacity is bounded; corrupt
storage is not silently reset. No reminder file exists until a mutation is confirmed.

Question repair handles a bounded set such as `When Mia finish school tomorrow?`
and `Når slutter Mia på skolen i morgen?`. It never guesses a different person's
name or rewrites device/memory/reminder actions. Replies remain English; this
is not unrestricted bilingual support or acoustic accent calibration.
`What did you hear me say?` echoes the recent received question in that exact
speaker/conversation for up to five minutes, in memory only, excluding obvious
credentials. It shows STT text, not a recording or proof of what was spoken.
Existing HA/provider retention policies are unchanged.

The current live Project Jarvis pipeline uses Home Assistant Cloud STT/en-US,
local Qwen reasoning and the existing English voice. STT language and TTS are
independent. Do not switch to Norwegian just because English has a Norwegian
accent. Compare intended question with STT text first, then trial supported
English variants on the same microphone without changing the saved voice.

## Household conversation understanding (0.45.63)

Flexible named-household fact questions use bounded local Qwen task interpretation,
code-owned approved facts, short composition and a grounding/usefulness check.
Exact birthdays/ages/jobs and clear commands retain their existing fast paths.
An explicit person focus survives direct answers: for example, ask an age, then
"And her school?", or ask about a day's plans, then "How old is she?".
Focus expires after five minutes and resets on speaker, profile revision, Norway
date, unrelated topic or action changes. A voice hint is relevance, not permission.

Compound facts and one person's calendar can share a connected reply. Calendar
reads/dates remain in the existing code-owned calendar path; missing calendars
never establish an empty or available day. Complex multi-person calendar requests
or mixed availability questions may require narrowing. This is bounded household
understanding, not a general autonomous agent or universal paraphrase guarantee.
No new actions, notifications, recordings, enrolment or voice-setting changes.

## Responsive voice follow-ups

Companion app text/native Assist replies stay on the original request until the
answer completes. A device ID alone does not imply support for Jarvis's separate
browser follow-up channel. Legacy browser event routes require an explicit
matching `jarvis-voice:` conversation and target; the reliable browser protocol
and explicitly configured external TTS routes retain their existing behavior.

Jarvis returns ordinary fast answers through the active Assist pipeline. When a
voice request is still running after the configured one-second backend deadline,
Jarvis gives a short progress response and continues the same bounded job. The
completed answer is spoken automatically through the conversation integration's
explicitly configured TTS entity and output media player. For the current
single-room setup, configure that media player as the development computer's
Home Assistant playback endpoint. Jarvis never selects an arbitrary speaker.

Later room satellites can reuse the same source identity and explicit route
contract so delayed answers return to the room that originated the request.

## Adaptive preference learning

M46 records repeated explicit temperature and lighting preferences as local
observations. An observation never affects Jarvis until three consistent
observations reach the evidence threshold and are automatically approved. Natural controls include
`I prefer the office at 21 degrees`, `What have you learned?`, `Why did you
learn office temperature?`, `That is wrong, use 20 degrees instead`, and
`Forget the office temperature preference`.

Disable the feature with the **Adaptive learning enabled** add-on option. Jarvis
does not adapt permissions, security actions, credentials, alarms or spending.
All discovered Home Assistant areas are canonicalized automatically. Optional
aliases can be added under `home_assistant.area_aliases` in Jarvis configuration,
for example `lounge: living room`.

## Blueprint planning

Ask Jarvis to create a blueprint, then describe the trigger, conditions and
actions. Jarvis generates an editor-compatible draft and asks for confirmation
before writing it under `blueprints/automation/project_jarvis`. Afterward, use
**Settings → Automations & scenes → Blueprints** to create an automation and
choose its entities. Jarvis does not create or enable an automation silently.

## Stewardship modes

Jarvis can maintain a confirmed Home, Away, Vacation, or Custom policy over
Home Assistant-authorized lights and climate entities. Try “I am travelling;
activate vacation mode until Sunday, keep the lights off, and keep the
temperature at 20 degrees.” Jarvis previews the complete scope and waits for
confirmation. Ask “stewardship status” to inspect it or “cancel stewardship
mode” to end it. Cancellation and expiry do not restore prior device states.
Locks, alarms, and cameras are never included by a stewardship mode.
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

Version 0.30.0 includes the optional complete Jarvis Dashboard System. Download the
`jarvis_ui` folder from the Project Jarvis Home Assistant repository and follow
its `README.md`. Installation remains explicit: the add-on is not granted
write access to Home Assistant's configuration directory. Register
`/local/jarvis/jarvis-ui.js?v=0.30.0` as a JavaScript module in Home Assistant

## Hybrid research and AI budget

Install and start **Project Jarvis Search**, then keep the default SearXNG URL
or provide another trusted SearXNG JSON endpoint in the Project Jarvis add-on
configuration. The default monthly external-AI budget is USD 10. Ask Jarvis
`show AI usage` or `show AI budget` to inspect the current month. Luna is the
normal reasoning model, Terra is attempted once after a provider failure, and
Sol requires an explicit request for premium reasoning.
dashboard resources. The Jarvis cards then appear in the visual card picker.
