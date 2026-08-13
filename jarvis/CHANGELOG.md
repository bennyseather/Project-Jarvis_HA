# Changelog

## 0.42.0

- Added bounded, local routine learning from Home Assistant state-change events.
- Require evidence on three separate days before suggesting a recurring routine.
- Added inspect, explain, forget, decline detection, and confirmed disabled automation drafts.
- Added the Jarvis Learning Insights sensor and visual-editor-compatible dashboard card.
- Excluded security-sensitive, guest, purchase, charging, and credential activity from learning.

## 0.41.0

- Added the full-width, editor-compatible Jarvis Heading card.
- Added an optional entity selector and default toggle behavior to Jarvis Button.
- Added searchable Jarvis icon catalogues to card and badge editors.
- Preserved the Home Assistant icon selector for MDI icon choices.

## 0.40.6

- Fixed corrupted degree symbols and temperature labels on climate cards.
- Use Home Assistant's configured Celsius or Fahrenheit unit for Mill heaters.
- Improved climate readout spacing and unavailable-temperature handling.

## 0.40.5

- Optimized the Jarvis press-to-talk animation for mobile and panel browsers.
- Reduced waveform layers and removed continuously repainted glow effects.
- Moved remaining animation to compositor-friendly transforms.

## 0.40.4

- Preserve the RSS Intelligence card scroll position across unrelated HA updates.
- Re-render the RSS feed only when its stories or configuration change.

## 0.40.3

- Keep Jarvis Voice card animations continuous across unrelated HA updates.
- Update the Voice Satellite only when its own entity or live status changes.

## 0.40.2

- Prevent unrelated Home Assistant state updates from restarting the RSS ticker.
- Re-render the ticker only when its RSS stories or configuration change.

## 0.40.1

- Add a per-feed story limit to the Jarvis RSS Intelligence card.
- Apply per-feed limits before the card-wide maximum to balance sources.

## 0.40.0

- Add the full-width, visual-editor-compatible Jarvis RSS News Ticker card.
- Add configurable speed, height, sources, story count, metadata, separators,
  pause behaviour, click behaviour, NSPanel sizing, and reduced-motion mode.

## 0.39.2

- Add a dedicated custom RSS feed input while retaining the built-in feeds.
- Merge, validate, deduplicate, and bound configured RSS sources.

## 0.39.1

- Preserve the complete bounded RSS headline list in concise voice responses.
- Continue applying normal concise voice limits to non-RSS replies.

## 0.39.0

- Add the Project Jarvis RSS add-on with bounded RSS/Atom fetching, sanitization, deduplication, feed health, and last-good caching.
- Add Home Assistant RSS story and feed-health entities plus refresh and mark-read services.
- Add deterministic Jarvis news commands and numbered follow-up story summaries; spoken replies omit URLs.
- Add a visual-editor compatible responsive Jarvis RSS Intelligence card with source/category grouping and lazy images.

## 0.38.6

- Resolve washing-machine, washer, dryer, and dishwasher status requests across all related permitted entities.
- Report appliance operating state and related sensors such as remaining time instead of stopping at the first exact-name entity.

## 0.38.5

- Stream clean Qwen audio as soon as the first generated segment is available.
- Pack adjacent sentences into fewer CPU generation calls and bound spoken replies to 260 characters.
- Persist a bounded cache of generated replies across Qwen worker restarts.
- Preserve customized buffering and spoken-length settings during migration.

## 0.38.4

- End sleep stewardship when a morning greeting or wake-up phrase is received.
- Restore the saved pre-sleep state and switch on authorized interior lights.
- Keep away and vacation stewardship active on morning greetings.

## 0.38.3

- Activate stewardship immediately without confirmation while retaining authorization, target caps, exclusions, restoration, and auditing.
- Keep an optional `require_confirmation` policy switch for installations that want the prior behaviour.

## 0.38.2

- Recognize natural departure and bedtime phrases and deterministically map them to confirmation-gated away, vacation, or sleep stewardship modes.

## 0.38.1

- Recognize natural return-home phrases such as “I'm home”, “back home”, “I'm back”, and “we're home” when ending stewardship and restoring prior states.

## 0.38.0

- Complete Autonomous Home Stewardship with vacation, away, sleep, home, and custom modes.
- Persist and restore authorized light and climate states when a mode ends or expires.
- Add optional bounded presence simulation and deduplicated exception notifications.
- Monitor smoke, gas, moisture, perimeter, unlocked-lock, and critical availability exceptions without taking security actions.
- Expose bounded stewardship status and audit history while preserving manual-override grace periods.

## 0.37.1

- Route natural questions about learned room preferences to adaptive memory instead of Home Assistant room-state enumeration.

## 0.37.0

- Expand adaptive preferences across rooms, weekdays/weekends, time periods, lighting, colour temperature, covers, speakers, and volume.
- Detect repeated multi-action routines and create inactive, approval-gated proposals only.
- Add durable per-category learning controls, explanations, corrections, deletion, confidence decay, and bounded audit history.
- Exclude security, safety, credential, purchasing, and vehicle-charging actions from automatic learning.

## 0.36.3

- Restore the compact light icon and add explicit ON/OFF controls.
- Fill washer progress from programme start to zero minutes remaining.
- Label sensor history with value and time axes.
- Group calendar agendas by day and add a dedicated month calendar card.

## 0.36.2

- Remove a duplicate module-level editor helper declaration that prevented the HACS JavaScript module from loading.

## 0.36.1

- Publish the dashboard resource at the root filename required by HACS.

## 0.36.0

- Refine light, cover, washing-machine, and sensor cards for touch use and real telemetry.
- Add Calendar, Glance, Home Alerts, Network / NAS, Climate Overview, Security Perimeter, and Energy Flow cards.
- Expand globally usable `jarvis:` icons and bound history/calendar loading for desktop and NSPanel performance.

## 0.35.3

- Canonicalize preference scopes against every discovered Home Assistant area.
- Treat articles, possessives, configured area aliases, and unique partial area names as the same room.
- Merge compatible legacy scope records safely while leaving ambiguous or conflicting records separate.

## 0.35.2

- Automatically approve safe preferences after three consistent observations.
- Keep observations inert until the threshold is reached and retain confidence, evidence, audit, correction, decay, and deletion controls.
- Continue permanently blocking security, alarm, credential, unlocking, and spending preferences.

## 0.35.1

- Keep equivalent preference wording such as “temperature to be 21 degrees” inside M46.
- Accept “approve” and “approved” as natural confirmation replies.
- Prevent the legacy repeated-memory learner from capturing the third M46 observation.

## 0.35.0

- Add M46 Adaptive Preference Learning with durable evidence and confidence tracking.
- Require explicit confirmation before an observed preference enters Jarvis context.
- Support natural inspection, evidence explanations, correction, deletion, stale-observation decay, and restart recovery.
- Reject security, credential, unlocking, alarm, and spending preferences from adaptive learning.

## 0.34.6

- Add an exact-match local ZHA quirk for the NamronAS 4512751 dimmer.
- Stop waiting for application responses the dimmer omits while preserving radio delivery errors.
- Cover on/off and level-control commands with installation, verification, and rollback guidance.

## 0.34.5

- Work around slow Qwen cold-cache playback by repeating the identical cached TTS request after generation.
- Keep the retry bounded to one pass after a one-second handoff delay.
- Apply the workaround to morning briefings and afternoon sign-offs.

## 0.34.4

- Request cached MP3 output at 44.1 kHz stereo for generated blueprint announcements.
- Let Home Assistant transcode Qwen PCM into a Google Cast-compatible format before playback.
- Apply the format consistently to morning briefings and afternoon sign-offs.

## 0.34.3

- Buffer the complete CPU-generated Qwen response before exposing audio to Home Assistant.
- Prevent Google Cast announcement sessions from timing out between the chime and delayed speech.
- Bound the pre-playback audio buffer and preserve Qwen as the primary voice.

## 0.34.2

- Preserve Home Assistant Jinja expressions with the required double braces in generated blueprints.
- Stop blueprint names at inline Trigger, Condition, or Actions fields.
- Continue weather, calendar, and speech steps when an individual office target is unavailable.

## 0.34.1

- Route blueprint requests to a dedicated review-first planner instead of entity-state queries.
- Add graphical trigger, action, target, weather, calendar, TTS, and speaker selectors.
- Add a tailored Office Work Greeting blueprint with morning, afternoon, next-workday, and fallback branches.
- Install generated YAML only after conversation-bound confirmation and keep automation creation inside Home Assistant.

## 0.34.0

- Add durable Home, Away, Vacation, and Custom stewardship modes.
- Preview and confirm the complete bounded policy before activation.
- Reconcile permitted lights and climate targets with expiry, exclusions, manual-override grace, partial-result reporting, and a bounded audit.
- Keep locks, alarms, cameras, permissions, entity state, and service execution owned by Home Assistant.

## 0.33.0

- Keep Qwen3-TTS as the primary voice regardless of generation latency.
- Cache repeated Qwen replies in bounded memory for near-immediate regeneration.
- Bound unusually long spoken payloads at natural sentence boundaries.
- Raise the CPU generation timeout and preserve partial Qwen streams without
  switching voices after playback data has begun.
- Report cache hits, misses, first-audio timing, and total generation timing.

## 0.32.3

- Repair partial Qwen model caches by downloading the complete repository snapshot.
- Validate the nested speech-tokenizer files before loading the local Qwen model.

## 0.32.2

- Add the packaged Qwen worker `/app` directory to `PYTHONPATH`.
- Fix local worker startup failing to import `qwen_engine`.

## 0.32.1

- Package an experimental local CPU Qwen3-TTS worker as a Home Assistant add-on.
- Use six bounded i5-8500 threads and float32 inference for CPU compatibility.
- Store public model weights under add-on `/data` and mount private references
  read-only from `/share`.
- Keep the external GPU worker optional rather than required.

## 0.32.0

- Add the optional private Qwen3-TTS 1.7B GPU worker and Wyoming proxy route.
- Cache the winning voice-clone reference prompt once per worker process.
- Stream the clean cloned voice without whole-response proxy buffering.
- Add Clean, Refined, Synthesized, Synthetic, and Metallic Qwen post-filters.
- Retain local Kokoro and Piper fallbacks without exposing private voice assets.

## 0.30.0

- Add the private M39 Piper medium voice as the default Wyoming TTS engine.
- Load and validate the model ZIP from `/share` without publishing voice data.
- Retain local neural and official Piper fallbacks with readiness diagnostics.
- Add reproducible Colab training/export fixes and private-model tests.

## 0.29.0

- Cache Chatterbox reference conditioning once and pre-warm the CPU model.
- Add adaptive, abbreviation-safe clause segmentation and crisp articulation.
- Add conditioning, warm-up and first-audio diagnostics.
- Give Jarvis v5 a subtle darker finish without slowing delivery.
- Preserve custom pitch settings while migrating untouched v5 defaults.

## 0.28.1

- Fix Chatterbox Nano reference conditioning on CPU by bypassing an upstream
  loudness conversion that promoted the approved reference to Float64.
- Restore the intended Jarvis v5 voice instead of falling back to Kokoro.

## 0.28.0

- Complete M37 Approved Jarvis Voice Integration.
- Bundle the approved v5 Chatterbox reference and dedicated balanced synthetic profile.
- Add bounded 25 ms long-pause compression for crisp staccato delivery.
- Migrate untouched legacy voice defaults while preserving explicit custom profiles.
- Retain warm CPU inference plus ordered Kokoro and Piper fallbacks.

## 0.27.2

- Remove inline source lists, Markdown source headings and generated citation markers at the final Home Assistant spoken-response boundary.

## 0.27.1

- Fix M36 startup by retaining validated personality defaults across configuration loading and service initialisation.

## 0.27.0

- Add M36 Contextual Jarvis Personality with unified configurable presentation controls.
- Add explicit proactivity and preferred-address app options plus local-first identity guidance.
- Add inspectable response-mode diagnostics while preserving exact policy and action results.

## 0.26.3

- Correct the Wyoming streaming capability flag so Home Assistant voice previews and pipelines send supported complete-text synthesis requests.

## 0.26.2

- Pin the official Chatterbox source revision that implements the documented `nano=True` CPU API missing from PyPI 0.1.7.

## 0.26.1

- Build Project Jarvis Voice on Python 3.13 so Chatterbox and Kokoro share NumPy 2.x without resolver conflicts.

## 0.26.0

- Add M35's warm CPU Chatterbox Nano engine with sentence-level Wyoming streaming.
- Include an original British reference generated from permissively licensed Kokoro output.
- Retain selectable Kokoro and automatic Piper fallbacks for A/B testing and resilience.
- Remove sources, Markdown links, and URLs at every spoken Home Assistant output boundary.
- Expose readiness, latency, fallback, and bounded error diagnostics while limiting inference threads.

## 0.25.1

- Treat native browser and Assist Satellite pipelines as voice interactions without requiring external speaker routing.
- Recognise list/show/name/what home queries and return bounded permitted floor light names.
- Report omitted item counts in long spoken listings.

## 0.25.0

- Add M34 Natural Jarvis Dialogue with explicit follow-up and correction guidance.
- Apply concise British-English personality presentation consistently across response paths.
- Remove source URLs from researched voice answers while preserving structured sources and text citations.
- Remove redundant spoken acknowledgement openings without changing facts or action results.

## 0.24.0

- Add bounded post-response listening for contextual voice follow-ups.
- Reuse Home Assistant conversation identity for up to three dialogue turns.
- Return safely to wake-word mode on silence, exit phrases, errors, or limits.

## 0.23.2

- Add a stronger Metallic voice-finishing profile.
- Raise the default voice pitch and accelerate delivery with bounded resampling.
- Add controlled modulation and quantisation to reduce human naturalness.

## 0.23.1

- Increase default neural voice speed and synthetic strength.
- Select the synthetic finishing profile by default.
- Normalize commas to avoid exaggerated pauses during speech.

## 0.23.0

- Add local Kokoro-82M neural synthesis with four British male voices.
- Keep bounded Jarvis finishing profiles and automatic Piper fallback.
- Load the neural model once and run CPU inference outside the event loop.

## 0.22.1

- Correct Wyoming JSON data-frame handling for Project Jarvis Voice discovery.
- Advertise the refined provider explicitly as Project Jarvis Voice.
- Preserve Piper audio format metadata through local refinement.

## 0.22.0

- Added the optional local Wyoming Piper voice processor.
- Added Refined, Synthetic, and Clean original British voice profiles.
- Added bounded strength and output-gain controls with direct Piper fallback.
- Kept generated PCM in memory only and preserved Home Assistant audio routing.

## 0.21.3

- Added authenticated Web Audio playback for browser-satellite TTS responses.
- Delayed wake-word rearming until spoken responses finish.

## 0.21.2

- Kept command audio streaming after wake-word detection so Home Assistant STT
  receives the complete spoken instruction.

## 0.21.1

- Fixed wake-pipeline validation by allowing Home Assistant to apply its
  default floating-point volume multiplier.

## 0.21.0

- Added an optional HTTPS browser voice satellite for Windows development.
- Added Home Assistant Assist pipeline wake-word and push-to-talk streaming.
- Added local mute, listening state, conversation continuity, and browser TTS.
- Added bounded duplicate-activation protection without storing audio.

## 0.20.0

- Added bounded episodic conversation summaries without raw transcript storage.
- Added local automatic low-sensitivity summaries and explicit Luna summaries.
- Added confirmation protection for sensitive conversation summaries.
- Added expiry, pinning, capacity controls, relevant retrieval, and hard deletion.
- Added natural commands to inspect, remember, pin, forget, and clear episodes.

## 0.19.0

- Added a safety-subordinate adaptive personality presentation layer.
- Added explicit warmth, moderate humour, and detailed verbosity options.
- Added relationship-preference inspection and selective deletion controls.
- Added explainable response styling and shorter voice-mode presentation.
- Added repetition, initiative, emotional-claim, and humour safety boundaries.

## 0.18.0

- Added optional local SearXNG search and bounded public-page evidence retrieval.
- Added Luna-to-Terra reasoning escalation and explicit-only Sol reasoning.
- Added persistent token/cost accounting, 70%/90% warnings, and a hard monthly
  budget limit without storing prompts or answers.
- Added an Ollama-ready provider-neutral reasoning contract.

## 0.17.1

- Prevented external “what changed” questions from being intercepted by the
  bounded Home Assistant state timeline.
- Added a safe research fallback for clearly current and identity questions
  when the language router returns malformed or unsupported output.

## 0.17.0

- Add M27 general OpenAI reasoning and automatic native web research.
- Route current, niche, uncertain, externally verifiable, and explicitly
  researched questions to a source-aware research provider.
- Add bounded URL citations, conversation-level enable/disable controls, and
  source follow-ups.
- Store research-derived information only after an explicit `remember this`;
  support permanent deletion with `forget this`.
- Preserve all existing Home Assistant authorization and confirmation rules.

## 0.16.0

- Add M26's typed, central, safety-subordinate Jarvis personality profile.
- Add British-English presentation and original refined synthetic voice
  guidance without actor or copyrighted-character imitation.
- Add durable address, humour, formality, and verbosity preferences with
  inspect, adjust, reset, and permanent-delete controls.
- Prohibit humour for failures, safety, emergencies, confirmations, and
  sensitive topics; personality never changes facts or action policy.

## 0.15.1

- Route goal management before general memory commands so goal deletion reaches
  the M25 store.
- Add `show goal`, `delete <name>`, `delete goal <name>`, and contextual
  `delete this goal` / `forget this goal` controls.

## 0.15.0

- Add explicit, durable, inspectable contextual household goals backed by
  Jarvis knowledge records.
- Build state-aware M24 plans that omit actions whose desired state is already
  satisfied.
- Add goal confidence, evidence, assumptions, explanations, and deterministic
  ambiguity handling.
- Add teach, list, explain, correct, and permanently delete controls.
- Prefer explicitly configured Home Assistant scenes and scripts, preserve the
  ten-action bound, and force confirmation for security-related goals.

## 0.14.0

- Keep badge editor forms mounted while Friendly name and other configuration
  fields emit changes, preventing focus loss after each typed character.
- Add bounded compound Home Assistant plans with parallel actions, explicit
  sequencing, current-state conditions, and exclusions.
- Validate every compound step through the existing capability, access, and
  risk gateways, with a maximum of ten resolved entity actions.
- Add one combined, conversation-bound confirmation, pre-confirmation
  correction, and explicit succeeded, skipped, failed, and partial outcomes.

## 0.13.2

- Keep the badge editor's Home Assistant data snapshot stable while it is open.

## 0.13.1

- Keep Jarvis badge editor forms mounted during frequent Home Assistant state
  updates so entity-selector menus remain open and usable.

## 0.13.0

- Add Jarvis Entity, Shortcut, Entity Progress, and Home / Away dashboard
  badges with graphical Home Assistant editors.
- Register all four badges in Home Assistant's badge picker.
- Apply shared Jarvis colours, icons, HUD framing, focus states, actions,
  numeric formatting, and reduced-motion behavior to badges.
- Remove the duplicated current-condition status from the Weather card.

## 0.12.3

- Prevent unrelated Home Assistant state deliveries from replacing the
  Weather card's forecast host while the native forecast is mounting.
- Compare stable current-weather fields rather than transient state-object
  identity and retry a forecast mount if its host changes mid-render.

## 0.12.2

- Refresh the Weather card's current-condition header when Home Assistant
  supplies or updates the configured weather entity.
- Keep the embedded three-to-five-day native forecast synchronized without
  rebuilding it for unrelated Home Assistant state changes.

## 0.12.1

- Add a visual-editor-compatible Car telemetry card.
- Add a three-to-five-day native Home Assistant forecast to the Weather card.
- Prevent Voice card text from overlapping its microphone control.
- Remove the duplicated state value from the Tile card.
- Label the mower interface as `Robotic Mower`.
- Expand Spotify with artwork, track, artist, playback, volume, and speaker
  output selection.
- Publish the frontend distribution for HACS-managed updates.

## 0.12.0

- Complete D3 Complete Jarvis Dashboard System.
- Expand the visual editor-compatible library from 16 to 32 cards.
- Add room, presence, weather, energy, fan, vacuum, lock, alarm, scene/script,
  timer, mower, washer, Spotify, EV charger, tile, and markup cards.
- Add shared design tokens, container-aware responsive layouts, room-detail
  views, and one-decimal numeric telemetry formatting.
- Preserve all D1 and D2 card types and Home Assistant ownership boundaries.

## 0.11.5

- Dispatch immediate actions through an isolated Home Assistant connection.
- Wait no more than one second for foreground service completion.
- Return an accurate `Action sent` acknowledgement when Home Assistant
  continues processing after the response deadline.
- Finish state reconciliation and action auditing asynchronously without
  blocking the conversation reply.

## 0.11.4

- Send bounded multi-device actions to Home Assistant in one service call.
- Reconcile Home Assistant service errors against the resulting entity states
  before reporting a device unavailable.
- Retry state reconciliation once after a short bounded settling interval.
- Reduce written-response latency for aggregate actions.

## 0.11.3

- Keep M23 follow-up scope stable per Home Assistant device, satellite, or user
  even when Home Assistant rotates conversation identifiers.
- Handle `turn back on`, `turn back off`, `turn them on`, and `turn them off`
  deterministically without an OpenAI fallback.
- Expand the bounded in-memory event buffer and retrieve recent changes per
  selected entity so unrelated home activity cannot hide relevant events.
- Reduce response latency for these follow-up actions by keeping them in the
  local deterministic path.

## 0.11.2

- Exclude area-level aggregate light helpers even when unavailable state data
  does not expose member entity IDs.
- Report unavailable action targets using Home Assistant friendly names and
  retain them for immediate follow-up questions.
- Support deterministic `turn back on` and `turn back off` follow-ups.
- Record successful aggregate actions directly in the bounded recent-change
  timeline and authorize it from the approved read set.

## 0.11.1

- Exclude aggregate light-group helpers from area-wide device actions.
- Find relevant area changes before applying the bounded timeline result limit.
- Correct singular device wording in action results.

## 0.11.0

- Complete M23 Whole-Home Situational Intelligence.
- Add bounded ephemeral floor, area, group, device, entity, and capability
  topology assembled from Home Assistant.
- Add deterministic compound state, health, exception, and low-battery
  questions with friendly-name responses.
- Add conversation-isolated spatial continuity for `there`, `them`, `all`,
  and `the rest`.
- Add recent-change answers through the permitted M8 in-memory timeline.
- Route explicit aggregate actions through the existing exact authorization
  gateway without granting new permissions.

## 0.10.1

- Expose the proactive voice opt-in in the Home Assistant add-on
  configuration while keeping it disabled by default.

## 0.10.0

- Complete M22 Proactive Assistance and Routine Intelligence.
- Add deterministic, privacy-bounded low-battery, reflective follow-up, and
  temporary repeated-event routine suggestions.
- Add durable suggestion lifecycle, provenance, confidence, expiry, cooldown,
  quiet hours, snooze, delivery deduplication, and inspectable suppressions.
- Add Home Assistant persistent-notification delivery and optional proactive
  speech through the explicitly enabled M20 voice route.
- Add natural controls for listing, explaining, applying, postponing,
  suppressing, clearing, and re-enabling suggestions.
- Route explicitly accepted actionable suggestions through the existing Home
  Assistant capability and risk gateway; unsolicited actions remain
  impossible.
- Migrate durable storage to schema version 4 without losing existing memory,
  knowledge, conversations, or reflections.

## 0.9.6

- Make the Light card's bulb icon the ON/OFF control.
- Remove the separate right-side toggle button, eliminating narrow two-column
  layout clipping on NSPanel.
- Expose current light state with the icon's active styling and
  `aria-pressed` value.

## 0.9.5

- Add an NSPanel-sized responsive Voice card.
- Reduce the microphone node, typography, padding, and signal-bar spacing on
  displays up to 900 pixels wide.
- Bound the signal visualization so it cannot push or hide the voice control.

## 0.9.4

- Add an NSPanel-sized responsive light-card layout.
- Allow the entity-name column to shrink without pushing the ON/OFF button
  outside the HUD frame.
- Reduce light-card spacing and control dimensions on displays up to 900
  pixels wide while preserving the desktop presentation.

## 0.9.3

- Enforce the same squared HUD shell on Voice and entity cards.
- Prevent controls from overflowing undersized Home Assistant section-grid
  rows.
- Add larger protected gutters and safe minimum row sizes for interactive
  cards.
- Mount the native live camera card before assigning Home Assistant state and
  request an immediate render, matching the known-working picture-entity
  configuration.

## 0.9.2

- Add a consistent four-pixel internal gutter around every Jarvis card so
  borders, hover movement, and glow effects cannot overlap adjacent cards.
- Allocate four Home Assistant grid rows to Camera and standard Voice cards,
  matching their rendered height.

## 0.9.1

- Render the Jarvis Camera card as an automatic Home Assistant live camera
  stream without requiring the user to open More Info.
- Preserve a local five-second snapshot fallback if the live card helper is
  unavailable.
- Add the same squared, chamfered HUD frame and segmented corners to the
  Jarvis Voice control node used by the rest of the card system.

## 0.9.0

- Add the complete D2 Jarvis UI Design System.
- Replace rounded presentation with squared, lightly chamfered HUD panels.
- Add shared cyan, amber, green, and red interface states with consistent
  hover, focus, touch, unavailable, and reduced-motion behavior.
- Add visually editable Button, Entity, Light, Switch, Slider, Climate, Cover,
  Media, Camera, Sensor, Security, Status, and Voice cards.
- Add an original `jarvis:` SVG icon set with automatic domain and
  device-class mapping and safe Home Assistant icon fallback.
- Add an Icon Catalog, local Entity Coverage audit, and component dashboard.
- Preserve the D1 card resource as a backward-compatible loader.
- Add an optional HACS Dashboard publication package without introducing a
  third-party runtime dependency.

## 0.8.2

- Add a locally bundled animated Jarvis voice card with microphone, interface
  rings, and responsive signal bars.
- Launch the preferred Home Assistant Assist pipeline through the supported
  dashboard action interface.
- Add matching Jarvis action cards for navigation and administration.
- Refine card depth, borders, hover states, typography, and panel styling.
- Preserve native Home Assistant entity tiles for device state and control.
- Add keyboard activation, reduced-motion support, resource registration, and
  upgrade instructions.

## 0.8.1

- Add the optional Jarvis Command Center Home Assistant UI pack.
- Add five responsive native dashboard views for command, rooms, environment,
  media and voice, and Jarvis administration.
- Add desktop and portrait Jarvis themes with original background artwork.
- Add a direct preferred-pipeline Assist launcher.
- Add Home Assistant OS installation, entity-mapping, update, and removal
  instructions.
- Keep the add-on isolated from Home Assistant configuration; UI installation
  remains an explicit user-controlled operation.

## 0.8.0

- Add durable, inspectable reflection records derived only from approved memories.
- Link related people, rooms, routines, preferences, and projects using bounded deterministic context.
- Detect conflicting repeated context and request an explicit correction instead of silently replacing it.
- Track low-confidence memories and relevant follow-ups without unsolicited notifications.
- Learn explicit response-style feedback immediately and keep it subordinate to privacy and safety.
- Consolidate exact duplicate memories without retaining deleted history.
- Add natural controls for learning opt-out, uncertainty, connections, provenance, and connected hard deletion.
- Migrate the durable SQLite schema transactionally while preserving existing memory.

## 0.7.1

- Match Companion microphone requests through either the direct device identity or an Assist satellite's registered device.
- Retry external TTS with provider defaults when a configured language or voice is unsupported.
- Reconnect once when a current-state read encounters a stale Home Assistant websocket.
- Resolve an unambiguous partial area phrase such as "all the office lights" deterministically.
- Add focused external-routing diagnostics while preserving local speech fallback.

## 0.7.0

- Add configurable Home Assistant-owned external voice output.
- Route only the selected microphone device to the selected TTS provider and media player.
- Preserve typed Assist while preventing duplicate local and external speech.
- Add voice-friendly response formatting and safe local fallback.
- Add session-bound natural yes, confirm, no, and cancel responses.
- Add the original calm, British-inspired Jarvis voice-character guidance.

## 0.6.0

- Add durable, conversation-isolated short-term memory using Home Assistant conversation IDs.
- Retain at most 20 conversations or 72 hours, with 100 messages per conversation and a 20-message model context.
- Promote schema-validated stable user context after three distinct repetitions.
- Require confirmation before sensitive information becomes durable memory.
- Add natural remember, recall, provenance, correction, forgetting, learned-memory, and recent-conversation controls.
- Preserve existing memory through a transactional SQLite schema upgrade.
- Add a centralized, configurable Jarvis character profile subordinate to privacy and safety.

## 0.5.7

- Exclude Home Assistant helper-group entities when reading all devices of one domain in an area.
- Keep the actual member lights, including individually area-assigned lights such as Blocks.

## 0.5.6

- Narrow oversized areas by an explicitly requested device domain on the same or next turn.
- Treat a bare configured group name as a read selection, never an implicit action.
- Preserve specific clarification text through the Home Assistant conversation bridge.

## 0.5.5

- Display Home Assistant friendly names in state summaries and clarifications.
- Reject oversized pending follow-ups before reading Home Assistant.
- Clear stale read context when a new explicit selection is unknown or oversized.
- Report the number of permitted entities when an area must be narrowed.

## 0.5.4

- Match bounded category phrases such as “porch lights” to permitted friendly names.
- Keep domain words as filters so light requests cannot select porch cameras or sensors.

## 0.5.3

- Resolve explicit group and area status questions before model routing.
- Expand light-group entity IDs to their member entities.
- Retain the last successful read scope for “them,” “there,” and “all of them.”
- Retain ambiguous read candidates so “both” reads every offered entity.

## 0.5.2

- Send bounded session history to OpenAI as real alternating conversation messages.
- Keep orchestration instructions separate from the current request and home context.
- Resolve clear follow-ups such as “all of them?” and “what about the rest?” without changing a status question into an action.

## 0.5.1

- Recognize Home Assistant light groups by membership, not only `group.*`.
- Resolve areas assigned directly to entities or inherited from devices.
- Read multi-device state from one bounded Home Assistant snapshot.
- Return deterministic candidates for duplicate friendly names.
- Report partial multi-device action outcomes.

## 0.5.0

- Add bounded area and group status summaries.
