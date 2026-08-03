# Project Jarvis UI 0.25.0

Project Jarvis UI is a reusable Home Assistant theme, card library, icon set,
and dashboard package. Cards use a squared technical HUD style and can be
added and edited from Home Assistant's visual dashboard editor.

Home Assistant continues to own entity state, permissions, and service calls.
The UI package does not change Jarvis memory or device authorization.

## Included files

- `jarvis-dashboard.yaml`: five responsive dashboard views.
- `jarvis-component-catalog.yaml`: card, icon, and coverage reference.
- `themes/jarvis-command-center.yaml`: desktop and portrait themes.
- `www/jarvis/jarvis-command-center-landscape.png`: desktop background.
- `www/jarvis/jarvis-command-center-portrait.png`: panel/mobile background.
- `www/jarvis/jarvis-ui.js`: complete Jarvis cards and `jarvis:` icons.
- `www/jarvis/jarvis-voice-card.js`: compatibility loader for D1 installs.
- `hacs.json` and `dist/Project-Jarvis_HA.js`: HACS publication package.
- `jarvis-command-center-preview.png`: original design preview.
- `configuration-snippet.yaml`: optional YAML dashboard registration.

## Install on Home Assistant OS

Use Studio Code Server, File editor, or Samba to access `/config`.

1. Copy both dashboard YAML files into `/config`.
2. Copy `themes/jarvis-command-center.yaml` into
   `/config/themes/jarvis-command-center.yaml`.
3. Copy the `www/jarvis` folder into `/config/www/jarvis`.
4. In Home Assistant, open **Settings -> Dashboards**, open the three-dot menu,
   and select **Resources**. Add `/local/jarvis/jarvis-ui.js?v=0.25.0`
   as a **JavaScript module**.
5. If you want the supplied dashboards, merge `configuration-snippet.yaml`
   into `/config/configuration.yaml`. Do not create a second `frontend:` or
   `lovelace:` key.
6. Run **Developer tools -> YAML -> Check configuration**.
7. Restart Home Assistant and hard-refresh the browser or app.

## Add and edit cards visually

1. Open any normal Home Assistant dashboard that you control.
2. Select **Edit dashboard**, then **Add card**.
3. Search for `Jarvis`.
4. Select a Jarvis card and configure its entity, friendly name, icon, accent,
   layout, and actions in the visual form.
5. Save the dashboard.

You do not need to use the supplied YAML dashboard. It is an optional
ready-made example; cards added to a normal storage-mode dashboard remain
editable through Home Assistant.

## Included cards

- Button and backward-compatible Action
- Entity, Light, Switch, and Slider
- Climate, Cover, Media, and Camera
- Sensor, Security, and multi-entity Status
- Voice, browser Voice Satellite, Icon Catalog, and Entity Coverage
- Room Summary, Presence, Weather, Energy, Fan, Vacuum, Lock, and Alarm Panel
- Scene / Script, Timer, Robot Mower, Washing Machine, and Spotify
- EV Charger, universal Tile, and Markup
- Car telemetry

## Included badges

- Entity
- Shortcut
- Entity Progress
- Home / Away

All four badges appear in Home Assistant's badge picker and include graphical
configuration editors.

All cards share hover/focus illumination, cyan/amber/green/red accent states,
keyboard controls, responsive sizing, and reduced-motion support.
Numeric sensor values displayed on Jarvis cards are limited to one decimal.

The Voice card dispatches Home Assistant's standard Assist action. The separate
Voice Satellite card can use a browser microphone over HTTPS for wake-word or
push-to-talk testing. Audio streams directly to Home Assistant's authenticated
Assist pipeline and is never stored by Jarvis. Muting the card closes its audio
track and releases the microphone.

## Jarvis icons

Use icons such as `jarvis:lightbulb`, `jarvis:spotlight`, `jarvis:plug`,
`jarvis:thermostat`, `jarvis:cover`, `jarvis:speaker`, `jarvis:camera`,
`jarvis:battery`, `jarvis:vehicle`, and `jarvis:automation`.

Jarvis cards select an icon from the entity domain and device class
automatically. A configured icon overrides it. The Icon Catalog card shows
every bundled name. The Entity Coverage card audits the current Home Assistant
state registry locally and lists domains using fallback icons; it does not
transmit or persist the registry.

## Entity mapping

The example dashboard uses accepted Project Jarvis test entities including
`light.blocks`, the upstairs-office and interior-light groups,
`camera.porch_camera`, and `media_player.loftstue_group`.

If an entity is unavailable or does not exist, edit that card and select the
matching entity from Home Assistant. The UI does not alter permissions.

## Optional HACS delivery

HACS is not required. The package includes a valid HACS Dashboard manifest and
distributable file for publication from the root of the public Project Jarvis
Home Assistant release repository. Once published:

1. Open **HACS**, then its three-dot menu and **Custom repositories**.
2. Add `https://github.com/bennyseather/Project-Jarvis_HA`.
3. Select **Dashboard** as the repository type.
4. Download **Project Jarvis UI**.
5. Confirm that HACS registered the resource, then refresh Home Assistant.

The theme, backgrounds, and example dashboards still require the manual copy
because HACS Dashboard repositories manage frontend resources rather than the
complete Home Assistant configuration.

## Update from an earlier UI release

Replace both dashboard files, the theme, and the `www/jarvis` folder. Replace
the old resource with `/local/jarvis/jarvis-ui.js?v=0.25.0`, restart Home
Assistant, and hard-refresh every client. The old JavaScript resource remains
a compatibility loader, but the new URL is recommended.

## Remove

Remove the two Jarvis entries from `lovelace.dashboards`, remove the Jarvis
theme and frontend resource, and restart Home Assistant. Existing dashboards,
entities, Project Jarvis memory, and automations are unaffected.
