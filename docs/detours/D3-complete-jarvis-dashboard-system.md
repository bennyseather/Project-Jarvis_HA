# D3 Complete Jarvis Dashboard System

Status: complete

## Outcome

Project Jarvis includes a complete, visual-editor-compatible Home Assistant
dashboard system with 33 cards, reusable design tokens and icons, container-
responsive layouts, polished room views, and desktop/NSPanel presentation.
Numeric telemetry shown by Jarvis cards is normalized to one decimal place.

## Architecture

- Home Assistant owns entities, state, permissions, services, automations,
  integrations, and dashboard configuration.
- Jarvis UI remains a local frontend resource. It does not modify Jarvis
  memory, reasoning, knowledge, orchestration, learning, or authorization.
- Cards use Home Assistant's standard frontend action and service interfaces.
- No third-party card or external network service is a runtime dependency.
- Existing D1 and D2 card types and configurations remain compatible.

## Card library

D3 retains the original 16 cards and adds Room Summary, Presence, Weather,
Energy, Fan, Vacuum, Lock, Alarm Panel, Scene / Script, Timer, Robot Mower,
Washing Machine, Spotify, EV Charger, Tile, and Markup.
The D3 acceptance update also adds a configurable Car telemetry card.

The Jarvis component library also includes four dashboard-header badges:
Entity, Shortcut, Entity Progress, and Home / Away. Each badge is registered
with Home Assistant's badge picker and has a graphical configuration editor.

All new cards register with the Home Assistant card picker and expose visual
configuration forms. Entity cards provide domain suggestions where applicable.

## Responsive system

The shared HUD shell defines stable colour, spacing, typography, control-size,
surface, and status tokens. Cards use container-aware compact layouts with
viewport fallbacks, bounded content, explicit Sections grid sizes, accessible
keyboard behavior, and reduced-motion support.

The supplied dashboard includes Command, Rooms, Environment, Media & Voice,
and Jarvis views plus room-detail subviews for the accepted example topology.

## Performance and privacy

Ordinary cards consume only the Home Assistant state objects supplied to them.
No card adds global listeners, storage, external requests, or background
registry scans. Camera streaming continues through Home Assistant's native
picture-entity card, with the existing bounded local snapshot fallback.
