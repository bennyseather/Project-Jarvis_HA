# D2 Jarvis UI Design System

Status: complete

Acceptance patch 0.9.1:

- Camera cards start Home Assistant's native live picture-entity stream when
  displayed, with a local refreshed-snapshot fallback.
- Voice cards use the same squared, chamfered and segmented control frame as
  the rest of the Jarvis card system.

## Outcome

Project Jarvis includes a reusable, visually editable Home Assistant interface
system. It provides a squared technical HUD theme, responsive backgrounds,
sixteen custom dashboard cards, an original `jarvis:` icon set, a component
catalog, and a local entity-coverage audit.

## Architecture

- Home Assistant owns entity state, user permissions, and service execution.
- Jarvis UI is a local frontend resource and does not modify Jarvis memory,
  orchestration, learning, or authorization.
- Cards use Home Assistant's standard `hass-action`, `hass-more-info`, and
  `hass.callService` interfaces.
- Card configuration is stored by Home Assistant in the selected dashboard.
- The card library does not send entity state or configuration outside Home
  Assistant.
- HACS is optional. No third-party card is a runtime dependency.

## Design system

- Square and lightly chamfered panels replace rounded cards.
- Cyan is the normal interface colour, amber is active, green is healthy, and
  red is warning or error.
- Shared styling covers hover, focus, pressed, unavailable, warning, compact,
  wide, mobile, and reduced-motion behavior.
- Background assets remain original Project Jarvis artwork.

## Editable card set

1. Button
2. Action (D1 compatibility alias)
3. Entity
4. Light
5. Switch
6. Slider
7. Climate
8. Cover
9. Media
10. Camera
11. Sensor
12. Security
13. Status
14. Voice
15. Icon Catalog
16. Entity Coverage

The cards register with the Home Assistant card picker. Entity-specific cards
also provide entity suggestions on Home Assistant 2026.6 and later.

## Icon system

The `jarvis:` icon set is registered through Home Assistant's custom icon-set
API. It contains more than fifty named icons covering lighting, power,
climate, covers, media, cameras, safety, sensors, rooms, appliances, vehicles,
scenes, scripts, automations, buttons, and updates. Domain and device-class
mapping provides automatic selection. Explicit card configuration always wins,
and unmapped entities retain their Home Assistant icon.

## HACS

The source package contains a HACS manifest and distributable JavaScript file.
It can be published at the root of the Home Assistant release repository as a
HACS Dashboard custom repository. Manual local installation remains supported.

## Acceptance boundary

D2 changes presentation only. Device actions performed by the control cards
are normal Home Assistant service calls made under the signed-in user's
permissions. The design system does not expand Project Jarvis access.
