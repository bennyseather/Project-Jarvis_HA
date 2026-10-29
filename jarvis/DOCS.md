## Conversational activity knowledge and departure planning (0.45.104)

Tell Jarvis a usual detail, for example: "Mia's band rehearsal usually takes
place at Haddal School. She needs her instrument and sheet music. It is two
minutes from home." Qwen binds exact user quotations to the existing person,
calendar source and activity title. Review the preview, then say "yes" or
"confirm household change" to save; cancel discards it. "Undo last household
change" uses the existing reviewed undo workflow. A new chat can ask where the
activity usually takes place or use its kit in preparation advice.

Follow-ups such as "She also needs a small towel" keep the recently selected
activity in that conversation. Unknown "I/my" still requires a named person or
an identified speaker. Dated exceptions are not saved as usual details. A venue
move withdraws its old home journey estimate; details for other activities remain.

Ask "What should Mia prepare for gymnastics tomorrow, and when should we leave?"
Jarvis refreshes the calendar, selects the relevant timed event and calculates
home departure from driving time plus a labelled ten-minute planning allowance
for arriving early/parking, or an explicit requested allowance. Existing home
location sharing approval and driving preference remain required. Fresh Entur
routes take precedence; compatible saved journey reports are labelled user
estimates. A specific current calendar venue overrides the usual venue and
prevents reuse of an incompatible saved journey time. Estimates exclude live
traffic; usual venues still need checking for the appointment. No calendar edit,
reminder, booking or household-device action is created by these read requests.

## Qwen-led conversation and tools (0.45.90)

Set conversation_mode to qwen_tools in /config/assistant_policy.json, alongside
its existing approved enabled flags. Legacy mode is the default if this field is
absent. Qwen interprets every normal conversational turn and selects one fixed
capability: identity, remembered details, household facts/plans, activity
preparation, calendar/profile editing, reminders, booked travel/airport briefs,
home tools, research, assistant settings, development proposals or general chat.
General conversation is answered by Qwen. Tools retain source checks, actual
permissions, date/age arithmetic, confirmed writes and durable action journals.
Pending explicit confirmations/cancellations can still be consumed by existing
code before model routing. No model-generated executable code, arbitrary endpoint,
authentication claim or replacement confirmation token is accepted.

Say Hi Jarvis,this is Benny speaking, or answer the name question after Who am I.
That creates an in-memory, 30-minute-idle reference for this authenticated
conversation/source/account/profile revision/day. It is not a voice match, live
presence or action authority. A real different voice match takes precedence.
Forget who I am clears this conversation reference without erasing household
facts or saved voice. Introductions are not stored as preferences. Name replies
to whose-detail questions apply only to that statement, not all future I/my.

The coordinator preserves original action text when delegating to existing
executors, and never claims a write from a general reply. Read tools still use
approved shared sources; missing sources remain unknown. A bounded model failure
returns a clear unavailable reply rather than silently reverting to a different
first-match router. Capability selection adds model time; measurements belong
to full installed text checks, not just a small model prompt benchmark.

## Natural preference intake (0.45.89)

Qwen judges whether a normal statement supplies a useful preference; no fixed
prefer/prefers verb rule decides its meaning. After a validated preference is
stored, Jarvis acknowledges completion. For an unrecognised speaker's first-person
statement, Jarvis asks whose preference it is and keeps the exact statement for
up to five minutes. Reply with the household member's name in the same chat.
This identifies only that statement's subject, not the signed-in user or voice.
A new topic, changed source/actor/profile/voice binding or expiry ends that link.
An exact old unattributed preference can be corrected in place when clarified.
The quoted source and the explicit clarification remain recorded for inspection.
Other useful reports continue through background learning and normal handlers.

## Assistant memory and initiative (0.45.87)

The opted-in assistant runs inside Jarvis, using the Node's qwen3:8b model locally.
Useful user statements are checked after the foreground conversation is quiet;
questions alone and assistant/web/calendar text are not learned as user facts.
Learning does not silently edit the confirmed household profile or calendar.
Shared knowledge remains shared; a voice match supplies relevance, not authority.

Enable only with /config/assistant_policy.json containing schema_version 1, explicit
boolean enabled/automatic_learning/automatic_travel/improvement_proposals flags,
memory_retention "until_deleted", transport_preference "driving_first", and
approval_source/recorded_on provenance. Missing file leaves this feature off.
Additional assistant tables live in the existing /config/jarvis.sqlite3 backup.

In Household > Assistant, inspect conversation details, source quotes, travel
briefs and proposals. Ask "Show learned memories", "What did Benny mention about
airport transport?", "Correct learned memory Mxxxxxxxx to ...", "Forget learned
memory Mxxxxxxxx", or "Forget all learned memories" (then confirm). "Pause
automatic learning" / "Resume automatic learning" and "Pause travel preparation"
/ "Resume travel preparation" are reversible. An unknown shared-account speaker
is never silently treated as Benny. Recent captures can need a short background
check; model/source failures are visible and are not claimed as completed work.

Travel preparation reads the next 30 days, refreshes changed flights and checks
unchanged briefs every six hours. Driving advice uses suggested two-hour airport
and fifteen-minute parking margins, not verified airline check-in cutoffs or live
traffic. Entur exact routes cover Norway; foreign airport information is researched
on official domains, without invented bus timetables. Arrival transfers still need
a supplied onward destination and route verification. Complete a question with
"Update travel brief Txxxxxxxxxx: leaving from [specific place], onward to [place]".
These details apply only to that source itinerary, and expire from applicability
when its flights change. Saved home is a planning origin, not live presence.

No background device operations, bookings, payments, calendar writes or messages
are added. Improvement ideas are proposals only; a future isolated patch/test/review
workspace is the next step toward Jarvis-assisted development. Existing action
confirmation remains in force. Audio/accent and real reminder tests stay held.

# Project Jarvis add-on

## Phone-appointment interpretation (0.45.80)

New unlabelled Familiekalender appointments are interpreted when the planner or
a relevant conversation reads them. The existing local Node model extracts people,
category, English activity and stated venue from English/Norwegian titles/notes.
One second local pass reviews the fields. Exact saved activity matches can supply
their confirmed person; usual venues do not become current locations. Named drivers
or organisers are not automatically attendees. Missing people/venues appear as
questions on the appointment; use Assign people/category or edit the phone entry.

This enriches the Jarvis index only. Google title, time, notes and location are
unchanged. Structured calendar locations win. Explicit manual/planner assignments
win over model results. Source-text/location edits and profile revisions invalidate
cached inference. Unavailable interpretation is retried after a short cooldown;
bounded reads process only a small number of new entries, with later refreshes
handling the rest. No cloud fallback, new automation, reminder or voice operation.
Source quotes, strict field checks and same-model review reduce errors but cannot
prove semantic correctness. Users can correct any assignment in the planner.

## Shared household planner (0.45.78)

The Household tab opens the existing `calendar.familiekalender`, backed by the
calendar already available on the household phone. Choose a member, a date and
day/seven-day view; filter by category or open the approved activity library.
Member selection is a relevance filter, not authentication. Connected Benny work
and travel calendars are read-only context, never the appointment destination.

Add appointment → choose members/category and Norway-local dates → Review →
Confirm and save. The review checks duplicates and visible member overlaps. A
review expires after five minutes or if household facts change. Ambiguous or
missing local times during daylight-saving transitions are rejected. All-day
last dates in the form are inclusive; Google receives an exclusive end date.
Creation is one appointment per save; manage recurrence and event edits using
the phone calendar. Titles/notes are data and cannot instruct model tool calls.

At deployment a single bounded import registers existing unlabelled entries as
Mia's, as previously confirmed. Newly discovered unlabelled phone entries are
Unassigned: select Assign people/category and review the annotation. This stores
only a Jarvis annotation; Google title/time/notes remain authoritative. Editing
an old annotated event's title/time on the phone can make it Unassigned again.
Jarvis-created entries carry a `JARVIS-PLAN/1` first line in their Google notes;
keep that line when editing on the phone. Removing it makes the event Unassigned.

`household_planner.sqlite3` stores attribution and reviewed-write receipts beside
the household profile and is covered by add-on data backups. The profile/voice
files are unchanged. Calendar entries are always read live. Timeout or uncertain
send outcomes block automatic resubmission: inspect the calendar before making
another appointment. No automatic cleanup, recurrence, reminders or audio runs.

The companion integration exposes authenticated `jarvis_conversation/planner`
commands, enforces HA entity permissions and keeps the bridge key server-side.
Use matching integration/frontend files. A separate card can be mounted as
`custom:jarvis-planner-card` after loading `/local/jarvis/jarvis-planner.js` as an
ES module; the existing Household component embeds it with its member directory.
The card alone also receives its directory in the agenda response.

## English organiser-note summaries (0.45.77)

For preparation answers, selected Norwegian notes can be summarised in English by
the existing local Node model. Only selected whole source clauses are submitted;
no calendar instructions can operate tools, save facts or edit appointments.
Each selected activity receives one summary, combining repetitions while keeping
distinct instructions, alternatives, conditions, times and restrictions. Code
checks schema, identities, lengths, numbers and key Norwegian/English terminology;
a separate bilingual call checks the summary against all original selected notes.
This same-model review is a safeguard, not independent proof of semantic accuracy.

At most one bounded correction is attempted. Each translation/review request has
a four-second provider limit; final English notes are wrapped in code-bound
appointment/date/venue text and are not put through a further free rewrite. If
checks, context validity or the model fail, the original-language source renderer
remains available. English-only notes and usual-profile prose keep their previous
composition path. There is no persistent translation cache or profile migration.
Usual advice remains qualified; a usual venue is never the current confirmed venue.
Saved voice/calibration is not changed and held audio/reminder tests stay held.

## Explicit same-activity presentation and organiser prose (0.45.76)

An exact profile can be linked explicitly to another existing profile for the
same household member, calendar and confirmed activity meaning. Use the existing
review/confirmation workflow, for example: Remember Alex's activity "Club B" in
the family calendar is the same activity as "Club A". Confirm with confirm
household change. These are stored facts, not model-created aliases. Existing
profiles remain valid without a link; same sport or same time alone never links
two activities. Views show the link and normal undo restores it. Deleting a
target or redefining its meaning clears affected links.

Preparation presentation coalesces only selected, explicitly linked records with
the same owner, calendar, start/end, day/all-day status and usual facts, and no
conflicting current locations. Missing location may use the other selected real
record's current venue, never a usual venue. All source identities stay available
for fresh lookups; source calendars and their entries are untouched. Identical
selected instruction clauses and usual notes are shown once. Different or
unlinked occurrences remain separate. Metadata reports selected-source and
presented-event counts.

Organiser-only preparation can now use the existing bounded local composition
and review path too. Safe negative/conditional source clauses are retained even
when the user asks only what to bring. Whole selected clauses stay in their
original language; the model must not translate, shorten a prohibition or invent
customary advice when none was supplied. The checked fallback also coalesces
explicit duplicates, so a failed model draft cannot restore the duplicate list.
This does not yet provide a checked English summary of Norwegian instructions.
Direct place questions remain short and do not read out unrelated instructions.

No new device/model permissions, calendar writes, automatic profile seeding or
voice changes occur. The optional same_activity_as field is accepted by this
version; downgrading to .75 or earlier requires the matching pre-link profile
backup, not just the old image. Audio/accent, real reminders and physical testing
remain held.

## Reviewed local-model preparation prose (0.45.75)

For preparation answers with selected confirmed activity-profile advice, the
existing Node model now writes the final prose from a small board of selected
events, whole organiser clauses and selected usual notes, plus the verified
source-bound summary. This is not another template-only wording layer. It is
also not a claim that every Jarvis request now goes through generative prose.
Direct venue questions, unresolved ambiguity and organiser-only replies retain
their existing source-bound path.

Code checks selected activities, times, current venues, required kit/preparation,
all-day status, unchanged protected instructions and usual venue/duration
qualifications. It rejects unsupported factual words, numbers, actions, links,
IDs and added questions. A separate call to the same local model reviews
grounding, completeness and naturalness. These checks reduce mistakes; the same
model reviewing itself is not independent proof of semantic correctness.

A rejected first draft gets at most one correction with specific missing-fact
feedback. There is no unbounded retry loop. Composition and review have a 7.5s
budget in addition to existing fact selection; eligible replies add two local
calls, or three if correction is needed. Failed, late, oversized or rejected
drafts fall back to the existing verified summary, not guessed prose. Reply
metadata distinguishes model composition from fallback and records call count,
elapsed composition time and a bounded fallback reason. Internal drafts are not
streamed or saved to memory. Code-owned suggestions/questions remain separate.

No model/tool permissions, calendar or household facts, saved voice or calibration
are changed. Cloud fallback stays disabled. Actual audio/accent, real-reminder
and physical tests remain held. Human text wording acceptance is still needed.

## Natural preparation summaries (0.45.74)

The existing local Node model still selects relevant appointments, complete source
clauses, approved usual notes and useful questions. The final source-bound prose
now combines same-person/day commitments and uses an exact confirmed activity's
readable meaning. Unknown or unsupported labels retain their original titles;
no new sport, attendance, venue or requirement is inferred. The display-only
surface form "orchestra practice" retains the stored "music orchestra practice"
meaning; it is not a learned alias or a new classification rule.

Selected routine notes become preparation advice such as having the usual kit
ready or following a confirmed usual routine. Simple positive preparation clauses
may follow grammatical "to"; negations, conditions and multi-sentence instructions
are retained whole rather than shortened into a different instruction. Current
organiser clauses remain exact quoted source text, including their language.
Owner-bound note selection and current-calendar overrides remain unchanged.

Missing current venues remain qualified as usual, not confirmed for the current
appointment. Usual duration still cannot fill an event end time. Events belonging
to different people or days are not collapsed into one shared commitment. All-day
entries stay all day. Date wording uses the already checked Norway reference day.
This is a bounded rendering improvement, not unrestricted model-generated prose
or proof of universal language understanding. No extra model pass or streaming of
unvalidated internal text is added. Saved household data and voice/calibration
are unchanged; actual audio/accent and real-reminder testing remain held.

## Confirmed activity profiles (0.45.73)

Jarvis can connect an exact recurring calendar title to a user-confirmed meaning
and usual details. The records live in the existing household profile, with its
review, confirmation, revision, history and undo workflow—not a separate memory
database or model weights. Shared-household approval is not voice authentication.
Nothing is inferred or seeded automatically, and calendar text never saves itself.

Use an explicit name, quoted title and calendar source (family, work or travel).
For example, using fictional information:

```text
Remember Mia's activity "Club" in the family calendar means "robotics"
confirm household change
Remember Mia's activity "Club" in the family calendar usually needs "project folder, water bottle"
confirm household change
Remember Mia's activity "Club" in the family calendar usually takes place at "Example Hall"
confirm household change
Remember Mia's activity "Club" in the family calendar usual preparation is "Check the project bag the evening before"
confirm household change
Remember Mia's activity "Club" in the family calendar usually lasts 60 minutes
confirm household change
Show Mia's activity profiles
```

Each change must be confirmed separately in the same conversation. An immediate
"yes" also confirms for the same current speaker context; uncertain identity does
not confer privileges. `also needs "another item"` appends instead of replacing
equipment. `Forget Mia's activity "Club" in the family calendar` proposes removal;
confirm it explicitly. `undo last household change` also requires confirmation.
History remains; removal is not secure erasure. A changed activity meaning clears
old equipment, preparation, venue and duration, as stated before confirmation.

Matching requires the same person, calendar source and full title; decorative
emoji do not change identity, but meaningful words, numbers and punctuation do.
Aliases, another person's entry or a different calendar do not inherit the record.
First-person edits require a current speaker match; unknown speakers must use a
name. Unsupported command forms request clarification rather than silent learning.

For fresh, permitted calendar appointments, local Qwen still decides useful
context and source clauses. Exact confirmed meaning can resolve an otherwise
generic title. Usual equipment/preparation is qualified and withheld when current
description details exist; current venues win. A usual venue is explicitly not
confirmed for the current appointment. Usual duration never fills a missing end
time; it is qualified context for an all-day entry only. No fresh appointment means
no invented attendance or schedule. Cancelled, conflicting or incomplete source
details conservatively block the usual mapping. Finite guards/model review cannot
prove every possible semantic conflict; uncertain cases should be clarified.

Up to 40 profiles and 12 equipment items per profile fit the existing bounded
household-document limit. No calendar writes, alarms, reminders or device actions
are added. Saved voice/calibration and model settings are unchanged. Actual audio,
accent and real-reminder acceptance remain on hold.

## Activity meaning and source evidence (0.45.72)

The local Node model still interprets supported calendar candidates, useful source
clauses and approved notes. A separate evidence guard now requires a requested
kind to be supported by a positive appointment title or description. Generic
training cannot establish swimming/gymnastics; general music cannot establish
piano or band. More specific evidence may support a broader request, not vice
versa. Venue names, emoji, family habits and equipment notes are not activity proof.

Known English/Norwegian activity words use a small explicit lexical vocabulary,
not model-generated aliases or new personal facts. Unrecognised labels need literal
source support; unsupported paraphrases may require clarification. This is not
complete multilingual understanding. Mixed-language activity labels in English
questions are tested; actual audio/accent tests remain held. Negative, uncertain,
conditional, cancelled or truncated source clauses cannot prove an activity kind.
Conflicting source clauses are treated conservatively and may require another check.

The question's activity follows venue/date continuations in the same valid scope.
An explicit appointment choice defines the referent, not a newly confirmed sport
or attendance fact. No clarification or organiser detail saves itself to memory.
Small broad-day preparation views of up to three source-bound appointments require
coverage of all of them. Larger views still use bounded model selection and identify
that more entries may exist. Code checks required coverage independently of model
output; the model still selects useful clauses,notes and missing-detail questions.

Date,owner,source,complete-clause and current-permission checks remain in force.
Same-model semantic review is a safeguard,not independent proof of all meanings.
Saved voice/calibration,models and permissions remain unchanged. No new device,
calendar,memory,notification or public-search action; real reminders stay on hold.

## Answering appointment clarifications (0.45.71)

After a plural venue question, a short appointment label answers Jarvis's pending
choice rather than starting a new routine question. The pending choice keeps the
person, date, original purpose and bounded source identities, not a cached venue
or model answer. It expires with the conversation scope and is invalidated by a
speaker, date, profile revision, permission or topic change.

Fresh permitted calendar records must still contain the selected appointment.
Unique title-token choices are source-bound directly; the existing local Node AI
interprets other short labels or translations with a separate relevance check.
Ambiguity and missing or changed records require clarification, not substitution.
The known person remains available for a subsequent birthday question. These
checks do not prove universal language understanding; model review is a safeguard.
Saved voice/calibration, permissions and actions are unchanged. Actual audio and
real-reminder acceptance stay on hold.

## Source-choice repair (0.45.70)

Event preparation now asks the existing local Node AI to mark fixed source event
slots and choose zero-based description-clause indices. It cannot generate excerpt
text,add events or choose clauses from an empty description. A separate decoder
rejects duplicate JSON keys,unknown/missing slots,non-boolean selections,invalid or
repeated indices,unused-event clauses and quota breaches before retrieving facts.
The earlier whole-clause,owner/date,note and source-provenance guards still apply.

Up to eight candidate appointments fit this bounded choice pass; up to three are
selected for a reply. Larger/overlong views request a shorter period rather than
silently dropping evidence. Period-only relevance follows already checked person
and date bounds. Activity-specific relevance and approved-note usefulness still
use local Qwen; same-model review is a safeguard,not proof of semantic correctness.
Date follow-ups retain an explicit activity filter. A plural previous selection
makes “Where is it?” ambiguous,so Jarvis asks which appointment while keeping the
known household person available for a birthday follow-up.

Multiple appointments without organiser details remain real appointments,not an
excuse to invent kit or repeat IDs. Missing venue/requirements and an unmatched
activity are distinct cases. Voice enrolment/calibration,existing model/permissions
and all device/calendar actions are unchanged. Audio and real-reminder tests stay
on hold; this repair adds no new notifications,recordings,searches or memory writes.

## Event context and remembered preparation (0.45.69)

Explicit questions such as “What should Mia prepare for tomorrow?”, “What should
Mia bring tomorrow?” and “Where is Mia's rehearsal tomorrow?” use the existing
local Jarvis Node model. It selects relevant appointments, extracts useful whole
description clauses and considers approved household notes. A separate bounded
local relevance check prevents substituting a different activity or adding an
unrelated note. This model check is a safeguard, not independent proof of meaning.

Locations and descriptions are opt-in source data, not tool instructions. Facts
are rendered from their exact event/owner/date or whole source clause; negation
and conditions are not removed. Norwegian source instructions remain quoted in
their original language; Jarvis's framing stays English. It does not infer the
venue from a title, assign transport or calculate a departure time without input.
Saved venues are remembered context, not proof of this appointment's current venue.
The current calendar venue takes precedence over a remembered venue.

Use the existing “Remember [named person and genuine activity detail]” workflow
and explicitly confirm to save knowledge. Model suggestions, organiser text and
answers to follow-up questions are not automatically saved. The same confirmed
note store is used; there is no second AI-owned household database. Retrieval is
bounded to four owner-scoped candidate notes, two selected notes and three events;
date-specific notes require the same event day. Relative/ambiguous dated notes are
excluded rather than guessed. A shorter date range helps when there is much data.

Short venue and date follow-ups retain the person/period only in a bounded,
speaker/revision/Norway-date-scoped session. Missing or unread calendars stay
unknown. No private calendar content is sent to search; embedded links are not
followed. No cloud fallback, model download, calendar write, reminder delivery,
device action or voice-enrolment change is introduced. Actual audio/accent and
real-reminder acceptance remain on hold. Existing mixed weather/departure/travel
questions retain their accepted pathways rather than being silently replaced.

## Purpose-first connected replies (0.45.68)

When asking how weather affects a person's plans, their actual connected calendar
entries come first. Same-day entries share one sentence; up to three entries are
included, with an explicit remainder where needed. No returned appointment does
not mean no plans; an unread calendar is reported differently from an empty one.

Weather stays local and conditional on spending time outside near home. This does
not establish the venue, whether an activity is indoors, attendance or transport.
Low precipitation probabilities keep their exact values but no longer force an
extra rain-preparation sentence. Other useful weather guidance remains bound to
its own date/condition/probability. Relative dates use the evidence's Norway date.

Technical contact prefixes can be removed using validated HA metadata. A generic
opening becomes a friendly contact label, not an invented window/door. Conflicting
type hints keep the original name. This changes reply wording, not HA entity names
or device configuration. Readings remain current reports, not physical verification.
Saved voice/calibration,permissions,models and action paths are unchanged. Audio,
accent and real-reminder testing remain held pending separate user acceptance.

## Source-bound connected replies (0.45.67)

Connected departure/home/weather questions now keep the factual parts outside
free-form model rewriting. A percentage remains precipitation probability for its
own forecast date; a current HA contact report never becomes Friday's home state.
Qwen chooses relevant ordering and conversational connectors around validated
clauses. Output remains prose, not a source-list display. Existing single-source
calendar interpretation, profile facts and birthday follow-ups retain their paths.

Cloudy weather with a low precipitation probability does not automatically suggest
rain preparation. Missing probability is not zero; contradictory condition/zero
probability fields prompt a recheck. Practical low/possible/wet wording uses a
code-owned heuristic, not a safety guarantee or knowledge of an activity's venue.
Current readings still need checking nearer departure; connected sources do not
confirm attendance. The local model's review is a usefulness check, not independent
proof. Travel/public summaries retain their existing source adapters and are not
newly independently extracted claims. This is a bounded repair, not a guarantee
of universal understanding. Saved voice is preserved; audio/reminder tests stay held.

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

### Calendar conversations (0.45.81)

In one HA Assist text conversation, request one appointment, answer the missing
details and check Jarvis's full review. Reply Yes only to save the reviewed draft;
Cancel discards it. Example: “Add a dentist appointment for Mia next Thursday at
14:00”, “One hour”, “The venue is Example Clinic”. A correction before Yes updates
the unsaved draft and produces a new review. Dates/times use Europe/Oslo, and the
review displays the actual date. Missing duration/venue is never guessed.

Existing appointment member/category corrections update the Jarvis catalogue
after review; Google time, title, notes and location remain unchanged. If the
appointment is ambiguous, select it first. Use your phone calendar for recurrence,
date/time/venue changes and deletion. An authenticated HA caller must have the
calendar entity permissions; recognised voice is relevance, never authentication.
An unknown speaker is asked whose appointment it is. Drafts expire after five
minutes and after context changes. An uncertain save must be checked in the
calendar before retrying. No new calendar or recurring automation is created.

Calendar clock formats (.82): 1600, 0930, 4 pm, 4:30 p.m., noon and midnight
are accepted for start/end times. The review still shows normalised Norway time.

### Existing appointments (0.45.83)

Find an appointment by person, title and day/week, select its number if several
match, then ask to move it, change its venue/title/person/category, or remove it.
Check the before/after review and confirm only that reviewed change. Cancel by
itself discards the review. A full request such as “Cancel that appointment”
prepares calendar removal and still requires confirmation; it never cancels a
provider booking. Repeating events affect one selected occurrence. Use the phone
for invited-guest events, whole-series editing and unsupported event types.

The original Google event identity stays in place, with only reviewed fields
patched and an If-Match version check. A changed phone event requires a new review.
Provider dispatch receipts live in Core's protected .jarvis-calendar-mutations.sqlite3;
the add-on retains the existing planner receipt. An uncertain save is not retried.
References: https://developers.google.com/workspace/calendar/api/guides/version-resources
and https://developers.google.com/workspace/calendar/api/v3/reference/events/patch

### Local readiness (0.45.86)

Startup warmup explicitly matches local_reasoning.context_tokens (currently4096)
and pins the existing configured Qwen runner. This avoids warming Ollama's wider
server default and then reloading the runner on the first bounded request.
A transport failure keeps the foreground request bounded, then schedules at most
one empty-prompt readiness check per cooldown in the background. Completed warmup
can clear the cooldown early; an unsuccessful check keeps the failure gate.
No user prompt replay, model pull, service restart or cloud fallback is involved.
Concurrent newer failures are preserved. A genuinely cold worker still needs load
time; other clients choosing a different model/context can require a reload.
References: https://docs.ollama.com/faq and https://docs.ollama.com/context-length

### Household conversation continuity (0.45.99)

Local Qwen can carry a read task between calendar summaries and preparation.
Follow-up people, dates and requested durations remain scoped to the signed-in
HA actor, conversation, source, profile revision, Norway day and matched voice.
The shared read context expires after ten idle minutes; sources are read again.
Calendar gaps and usual work times do not establish actual availability. Any
travel or transition time remains unknown unless separately sourced.

Relevant retained user reports can personalise reasoning and general chat.
They remain attributed reports, with original date windows, rather than calendar
appointments or canonical routine edits. Memory retention is unchanged. The
existing correction/forget controls apply; a deletion during reasoning withdraws
the stale answer. No new booking, device, message or self-development authority
is granted. Existing calendar confirmations and saved voice are unchanged.

### Interactive driving routes (0.45.100)

Qwen selects local_route for requests to check driving time, including a venue
statement followed by a question. The fixed tool extracts exact user place names,
queries the official Entur geocoder/router and supplies the verified duration.
Named public origins and destinations work without reading the saved home point.
A town-level result does not establish the exact gym entrance or parking time.
No live traffic is claimed. General public transport is not implemented in this
interactive tool; existing airport public-transport alternatives are unchanged.

Interactive saved-home routing is disabled unless assistant_policy.json contains
an explicitly approved interactive_home_routing object: enabled boolean, a nonempty
approval_source string, and recorded_on YYYY-MM-DD. It is optional and defaults off.
A maintainer records it only following direct human approval to send the saved home
coordinates to Entur for route checks. Conversation or model output cannot grant
that authority. Home coordinates remain outside Qwen inputs, replies and logs;
when enabled, the external routing provider necessarily receives the route points.
No such production approval is enabled by this release.


### Contextual driving follow-ups (0.45.101)

After a dated household dinner-planning discussion, ask What is the travel time?
The routing tool re-reads the following appointment and its exact-scoped saved
activity venue. It can use home as a labelled dinner planning origin and the
configured driving-first preference. A town-level estimate is not the exact
venue entrance, live traffic, parking or a claim about current presence.

Short replies such as home or driving fill the pending route without dropping
its other fields. Pending and completed routes expire after five minutes and
are invalidated by changes to the read person/date scope; normal conversation
account/source/profile/day/voice binding also applies. Specific current calendar
venues override usual venues. Ambiguous endpoints still need clarification.
The existing explicit interactive_home_routing approval remains required; this
release does not grant or broaden sharing. No calendar or device write occurs.


### Automatic dinner and journey budgets (0.45.102)

When asking whether dinner fits between one person's two dated appointments,
Jarvis checks both driving journeys without requiring a separate route question.
The configured driving-first preference and existing explicit home-to-Entur
approval are required. Qwen interprets the eating location: home can be a labelled
planning assumption if unspecified; an explicitly elsewhere meal never silently
routes through home. No new sharing permission is granted by this release.

The first route departs after the earlier activity; the second arrives by the
next activity. Code combines both estimates with the user-supplied meal duration
and reports spare minutes or a shortfall. An unknown duration prompts once while
showing the estimated driving budget. Unknown venues/routes stay unknown: a
partial budget cannot establish that the whole plan fits. General traffic,
parking, preparation and attendance remain unverified.

When one activity venue is missing, supply its place name or state where it is.
Qwen extracts the exact user quote, then the fixed route tool recalculates. This
venue is an expiring conversation report, not a saved profile/calendar update.
It is bound to the actor/chat/source/day/profile/voice, current person/date and
exact event source/title/times/current venue. Later meal-duration replies reuse
it within that scope; changed events/scopes or expiry withdraw it.


### Reported journey times in a meal plan (0.45.103)

When Jarvis asks for the missing activity location, a reply such as In Haddal,
2 minutes from home can supply the journey estimate directly. Qwen identifies
which pending activity/home journey the reply concerns and copies its exact
place/duration quote. Code validates the stated duration and performs arithmetic.
It does not replace dinner length or infer minutes from a distance or clock time.

The answer distinguishes your estimate from the route service estimate. A
reported journey can complete a planning budget without geocoding its broad
place label. It is not independently verified, live traffic or a durable fact.
These reports share the existing five-minute/event/account/conversation binding,
are retained for a revised meal duration within that scope, and are withdrawn
when the source event or scope changes. No calendar/profile/memory write occurs.
