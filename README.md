# Project Jarvis for Home Assistant

This repository publishes the Project Jarvis Home Assistant add-on,
conversation integration, and optional Jarvis UI Design System.

## Add-on installation

Add this repository to **Settings -> Add-ons -> Add-on Store -> Repositories**:

`https://github.com/bennyseather/Project-Jarvis_HA`

Install **Project Jarvis**, configure its OpenAI and bridge API keys, and then
install the companion files from `custom_components/jarvis_conversation`.
Detailed instructions are in `jarvis/DOCS.md`.

## Project Jarvis 0.14.0

Version 0.14.0 adds M24 Compound Home Orchestration. Jarvis can now validate
and execute bounded parallel actions, explicit `then` sequences, current-state
conditions, and exclusions across permitted Home Assistant entities. Every
step continues through the existing authorization and risk gateways, plans are
limited to ten resolved entity actions, and partial outcomes are explicit.
This release also fixes uninterrupted typing in Jarvis badge Friendly name
fields.

The `jarvis_ui` folder contains:

- Squared Project Jarvis desktop and panel themes.
- Responsive original background artwork.
- Thirty-three visually editable Jarvis dashboard cards.
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
