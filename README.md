# Project Jarvis for Home Assistant

This repository publishes the Project Jarvis Home Assistant add-on,
conversation integration, and optional Jarvis UI Design System.

## Add-on installation

Add this repository to **Settings -> Add-ons -> Add-on Store -> Repositories**:

`https://github.com/bennyseather/Project-Jarvis_HA`

Install **Project Jarvis**, configure its OpenAI and bridge API keys, and then
install the companion files from `custom_components/jarvis_conversation`.
Detailed instructions are in `jarvis/DOCS.md`.

## Project Jarvis RSS Intelligence 0.39.1

Version 0.39.1 adds a private RSS/Atom add-on, Home Assistant RSS entities and
services, deterministic Jarvis news summaries with spoken-link suppression,
and a responsive visual-editor RSS card. Feed content is sanitized, bounded,
deduplicated, cached locally, and cannot authorize Home Assistant actions.

## Project Jarvis Stewardship Departure Hotfix 0.38.2

Version 0.38.2 recognises natural departure, travel, and bedtime phrases and
maps them to confirmation-gated away, vacation, or sleep stewardship modes.

## Project Jarvis Stewardship Return-Home Hotfix 0.38.1

Version 0.38.1 recognises natural return-home phrases when ending stewardship
and restoring captured light and climate states.

## Project Jarvis Autonomous Home Stewardship 0.38.0

Version 0.38.0 completes bounded vacation, away, sleep, home, and custom
stewardship modes. Jarvis can reconcile authorized lights and climate targets,
optionally simulate presence with at most two authorized lights, monitor and
deduplicate safety/perimeter/availability exceptions, restore captured light
and climate states on exit or expiry, honour manual overrides, and expose an
inspectable audit. Locks, alarms, cameras, and security services remain outside
automatic execution, and Home Assistant remains the sole execution authority.

## Project Jarvis Preference Query Hotfix 0.37.1

Version 0.37.1 answers natural preference questions from approved adaptive
memory instead of treating the room name as a request to enumerate devices.

## Project Jarvis Adaptive Self-Learning 0.37.0

Version 0.37.0 extends Jarvis's durable three-observation preference learner
across rooms and contextual weekday/weekend or time-of-day scopes. It learns
low-risk climate, lighting, cover, speaker, and volume preferences; detects
repeated compound routines as inactive proposals; provides durable category
controls, explanations, correction, deletion, and bounded auditing; and never
automatically learns security, safety, credential, purchase, or EV-charging
actions. Home Assistant remains the sole execution authority.

## Project Jarvis Dashboard Refinement 0.36.3

Version 0.36.3 restores compact light icons with separate ON/OFF controls,
makes washing-machine progress adapt to each programme, labels real sensor
history axes, groups agenda appointments by day, and adds a dedicated month
calendar card.

## Project Jarvis Dashboard Module Hotfix 0.36.2

Version 0.36.2 removes a duplicate module-level editor helper declaration
that prevented Home Assistant from registering any Jarvis custom elements.

## Project Jarvis Dashboard HACS Hotfix 0.36.1

Version 0.36.1 restores every Jarvis custom card after the 0.36.0 HACS
package omitted the root `Project-Jarvis_HA.js` resource expected by its
manifest. Dashboard behaviour is otherwise identical to D4.

## Project Jarvis Dashboard Refinement and Expansion 0.36.0

Version 0.36.0 completes D4. It improves touch controls, removes the cover Stop
button, calculates washer completion from minutes remaining, and replaces
decorative sensor traces with bounded Home Assistant history. It also adds
Calendar, Glance, Home Alerts, Network / NAS, Climate Overview, Security
Perimeter, and Energy Flow cards with visual editors and responsive NSPanel
layouts. The expanded `jarvis:` icon set is globally available to ordinary
Home Assistant cards and entity customizations.

## Project Jarvis Adaptive Preference Learning 0.35.3

Version 0.35.3 adds threshold-gated adaptive preference learning and resolves
preference scopes against every discovered Home Assistant area. Articles,
possessives, configured aliases, and unique partial room names share one evidence
ledger. Jarvis accumulates
repeated temperature and lighting preferences and automatically approves a safe
preference after three consistent observations. Nothing learned affects
reasoning before that threshold.

Natural controls include “What have you learned?”, “Why did you learn office
temperature?”, “That is wrong, use 21 degrees instead”, and “Forget the office
temperature preference”. Security, credentials, alarm, unlocking and spending
categories are denied. Observations, approvals, corrections, deletion and a
bounded audit survive restarts in Jarvis SQLite storage.

The prior release also includes an optional, exact-match local ZHA quirk for the NamronAS
4512751 dimmer. The device executes commands but omits the application response
expected by ZHA; the quirk prevents that omission from blocking automations while
preserving genuine radio delivery failures. Installation is intentionally manual.

## Project Jarvis Cold-Cache Cast Handoff 0.34.5

Version 0.34.5 works around slow CPU Qwen cold-cache playback by making one
bounded repeat of the identical cached TTS request after a one-second handoff.
The first pass completes generation; the second lets Google Cast retrieve the
finished MP3. This temporary compatibility path applies to both briefing branches.

## Project Jarvis Cast-Compatible Briefings 0.34.4

Version 0.34.4 makes generated Office Work Greeting blueprints request cached
MP3 speech at 44.1 kHz stereo. Home Assistant completes and transcodes the Qwen
audio into a Google Cast-compatible format before starting morning briefings
or afternoon sign-offs.

## Project Jarvis Reliable Cast Voice 0.34.3

Version 0.34.3 buffers the complete CPU-generated Qwen response before Home
Assistant starts playback. Google Cast speakers therefore receive continuous
audio after their announcement chime instead of timing out while Qwen is still
generating later sentences. The buffer is bounded, Qwen remains the primary
voice, and the existing fallback path is retained for genuine failures.

## Project Jarvis Blueprint Repair 0.34.2

Version 0.34.2 corrects Jinja escaping in generated blueprint YAML, bounds
inline name parsing, and prevents an unavailable office target from stopping
the weather, calendar, and spoken briefing stages.

## Project Jarvis Blueprint Planner 0.34.1

Version 0.34.1 prevents blueprint requests from falling through to Home
Assistant entity-state queries. Jarvis now gathers the blueprint description,
generates structurally validated editor-compatible YAML, previews the full
configuration write, and installs it only after explicit confirmation. The
Office Work Greeting design includes reusable selectors plus weather, calendar,
TTS, next-workday, and outside-hours branches. Home Assistant remains the owner
of the resulting blueprint and every automation created from it.

## Project Jarvis Home Stewardship 0.34.0

Version 0.34.0 adds confirmed, restart-safe Home, Away, Vacation, and Custom
stewardship modes. Jarvis can maintain permitted light and climate policy with
timed expiry, exclusions, manual-override grace, bounded reconciliation and
audit reporting. Home Assistant remains the sole owner of entities, state,
permissions, services, and automations; locks, alarms, and cameras stay out of
mode scope.

## Project Jarvis Responsive Qwen Voice 0.33.0

Version 0.33.0 keeps Qwen3-TTS as Jarvis's primary voice even on the temporary
CPU host. Repeated replies use a bounded in-memory audio cache, unusually long
spoken payloads are shortened at natural boundaries, CPU generation receives a
five-minute budget, and diagnostics expose cache and generation timings. Local
Piper and Kokoro voices remain failure-only fallbacks.

## Project Jarvis Local Qwen Worker 0.32.3

Version 0.32.3 prefetches and validates the complete Qwen model snapshot before
loading it, repairing partial caches that omitted the nested speech tokenizer.

## Project Jarvis Local Qwen Worker 0.32.2

Version 0.32.2 exposes the worker's `/app` directory on `PYTHONPATH`, allowing
the Home Assistant entrypoint to import the packaged Qwen engine and server.

## Project Jarvis Local Qwen Worker 0.32.1

Version 0.32.1 packages the Qwen3-TTS 1.7B worker as an experimental amd64
Home Assistant add-on. It uses CPU float32 inference, six bounded worker
threads, persistent `/data` model caching, and read-only private reference
files from `/share`. This allows the i5-8500/64 GB Home Assistant host to be
benchmarked before any external GPU or VPN is considered.

## Project Jarvis Voice 0.32.0

Version 0.32.0 adds M41 Qwen Jarvis Voice Runtime. The Home Assistant voice
add-on can route its existing Wyoming service to a warm private Qwen3-TTS 1.7B
GPU worker, stream clean audio sentence by sentence, and apply selectable
Clean, Refined, Synthesized, Synthetic, or Metallic finishing filters. Private
reference audio, its transcript, and model caches remain outside Git and HACS.

The worker is optional and independently deployable. Piper M39/M40, Chatterbox,
Kokoro, and official Piper fallback behavior remain available.

## Project Jarvis Voice 0.31.0

Version 0.31.0 introduces M40, an expanded private Piper medium voice trained
from 799 approved British English clips. The add-on loads the separately
transferred `jarvis-piper-m40.zip` package from Home Assistant `/share`, serves
`jarvis_m40` through Wyoming, and retains M39 as a rollback option. Source
recordings, transcripts, caches, and checkpoints remain private.

## Previous M39 clarity release

Version 0.30.1 adds a reversible M39 clarity baseline. Piper inference noise is
reduced, a gentle high-frequency hiss filter is enabled, and synthetic DSP is
bypassed while `clarity_mode` is active. The private voice package is unchanged.

## Project Jarvis 0.30.0

Version 0.30.0 completes M39 Dedicated Jarvis Piper Voice. The voice add-on now
loads the private `jarvis-piper-m39.zip` package from Home Assistant `/share`,
serves the dedicated `jarvis_m39` voice through Wyoming, targets 1–4 second CPU
responses, and keeps local Kokoro and Piper fallbacks. The dataset, checkpoints,
and trained model remain outside the public repository. The reproducible Colab
notebook includes checkpoint migration, live output, Piper native-extension
building, and PyTorch legacy ONNX export compatibility.

M38 added cached
conditioning, startup pre-warming, adaptive clause segmentation, conservative
articulation controls, timing diagnostics and a subtly darker v5 finish.
Explicit custom voice profiles remain unchanged and Kokoro/Piper fallbacks remain available.
It retains the 0.27.2 spoken-source filtering and M36 startup fix. M36 adds unified configurable
formality, warmth, verbosity, restrained humour, proactivity and preferred
address, with inspectable per-conversation presentation diagnostics. It retains
the Wyoming voice-preview fix and official Chatterbox source revision containing the
documented Nano CPU API. Python 3.13 keeps Kokoro and Chatterbox on a shared
NumPy 2 compatibility boundary. M35 adds a warm,
CPU-bounded Chatterbox Nano engine, sentence streaming, and ordered Kokoro/Piper
fallbacks. All spoken reply paths now remove source sections and URL addresses,
while typed answers retain citations. M34 Natural Jarvis Dialogue provides follow-ups, clear corrections,
British-English personality presentation, and voice-optimised answers now form
a more coherent bounded conversation. Researched voice answers omit source URLs
while text responses retain citations. The optional Project Jarvis Voice app transparently processes local Piper PCM through bounded
British technical voice profiles and returns it through the Wyoming protocol.
It includes Refined, Synthetic, and Clean profiles, explicit strength and gain
controls, an immediate direct-Piper fallback, and no stored audio or cloud TTS.
Home Assistant continues to own pipelines, devices, permissions, and routing.

The `jarvis_ui` folder contains:

- Squared Project Jarvis desktop and panel themes.
- Responsive original background artwork.
- Thirty-four visually editable Jarvis dashboard cards.
- Four visually editable Jarvis dashboard badges.
- More than fifty `jarvis:` entity icons.
- Automatic icon mapping and a local entity-coverage audit.
- An optional component-catalog dashboard.

See `jarvis_ui/README.md` for manual installation and visual-editor usage.

The `jarvis_voice` folder contains the optional local Piper voice processor.
Install Piper first, then follow `jarvis_voice/DOCS.md`.

## Optional HACS installation

This release repository is also prepared as a HACS Dashboard custom repository.
In HACS, add this GitHub URL under **Custom repositories**, select
**Dashboard**, and download **Project Jarvis UI**.

HACS installs the card and icon JavaScript resource. The theme, background
assets, and example dashboards remain an explicit manual installation from
`jarvis_ui`, because HACS Dashboard repositories do not manage complete Home
Assistant configuration.

## Boundaries

Home Assistant remains responsible for devices, entities, permissions,
automations, state, and service execution. Jarvis owns memory, context, home
knowledge, orchestration, and learning. The UI package changes presentation
only and does not expand Jarvis permissions.
