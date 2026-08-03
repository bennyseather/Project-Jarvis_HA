# Project Jarvis for Home Assistant

This repository publishes the Project Jarvis Home Assistant add-on,
conversation integration, and optional Jarvis UI Design System.

## Add-on installation

Add this repository to **Settings -> Add-ons -> Add-on Store -> Repositories**:

`https://github.com/bennyseather/Project-Jarvis_HA`

Install **Project Jarvis**, configure its OpenAI and bridge API keys, and then
install the companion files from `custom_components/jarvis_conversation`.
Detailed instructions are in `jarvis/DOCS.md`.

## Project Jarvis 0.28.1

Version 0.28.1 completes M37 Approved Jarvis Voice Integration with the bundled
v5 Chatterbox reference, crisp staccato delivery, balanced synthetic/metallic
finishing and safe migration from untouched legacy defaults. Explicit custom
voice profiles remain unchanged and Kokoro/Piper fallbacks remain available.
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
