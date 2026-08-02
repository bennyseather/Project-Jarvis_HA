# Project Jarvis for Home Assistant

This repository publishes the Project Jarvis Home Assistant add-on,
conversation integration, and optional Jarvis UI Design System.

## Add-on installation

Add this repository to **Settings -> Add-ons -> Add-on Store -> Repositories**:

`https://github.com/bennyseather/Project-Jarvis_HA`

Install **Project Jarvis**, configure its OpenAI and bridge API keys, and then
install the companion files from `custom_components/jarvis_conversation`.
Detailed instructions are in `jarvis/DOCS.md`.

## Project Jarvis 0.21.3

Version 0.21.3 adds M31 Voice Activation and Wake-Word Routing, including the
Home Assistant-compatible wake-pipeline input correction and uninterrupted
command audio after wake detection and authenticated browser TTS playback.
Home Assistant
continues to own wake-word detection, speech-to-text, text-to-speech, devices,
and audio routing. The optional browser Voice Satellite provides authenticated
wake-word and push-to-talk testing from a Windows PC, returns speech to that
browser, exposes immediate mute controls, and stores no audio. Duplicate voice
activations are idempotent and confirmations remain bound to their conversation.

The `jarvis_ui` folder contains:

- Squared Project Jarvis desktop and panel themes.
- Responsive original background artwork.
- Thirty-four visually editable Jarvis dashboard cards.
- Four visually editable Jarvis dashboard badges.
- More than fifty `jarvis:` entity icons.
- Automatic icon mapping and a local entity-coverage audit.
- An optional component-catalog dashboard.

See `jarvis_ui/README.md` for manual installation and visual-editor usage.

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
