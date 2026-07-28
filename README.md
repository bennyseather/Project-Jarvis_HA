# Jarvis Command Center

Jarvis Command Center is an optional, native Home Assistant dashboard and
theme. It uses built-in Sections, heading, tile, shortcut, weather, markdown,
and picture-entity cards. It does not require HACS or third-party cards.

## Included files

- `jarvis-dashboard.yaml`: five responsive dashboard views.
- `themes/jarvis-command-center.yaml`: desktop and portrait themes.
- `www/jarvis/jarvis-command-center-landscape.png`: desktop background.
- `www/jarvis/jarvis-command-center-portrait.png`: panel/mobile background.
- `www/jarvis/jarvis-voice-card.js`: local Jarvis voice and action cards.
- `jarvis-command-center-preview.png`: design preview.
- `configuration-snippet.yaml`: the configuration entries required by Home
  Assistant.

The preview communicates the visual direction and contains illustrative
values. The installed dashboard always displays live Home Assistant entity
state.

## Install on Home Assistant OS

Use Studio Code Server, File editor, or Samba to access `/config`.

1. Copy `jarvis-dashboard.yaml` into `/config/jarvis-dashboard.yaml`.
2. Copy `themes/jarvis-command-center.yaml` into
   `/config/themes/jarvis-command-center.yaml`.
3. Copy the `www/jarvis` folder into `/config/www/jarvis`.
4. In Home Assistant, open **Settings -> Dashboards**, open the three-dot menu,
   and select **Resources**. Add `/local/jarvis/jarvis-voice-card.js?v=0.8.2`
   as a **JavaScript module**.
5. Merge the contents of `configuration-snippet.yaml` into
   `/config/configuration.yaml`. Do not create a second `frontend:` or
   `lovelace:` key if one already exists.
6. Run **Developer tools -> YAML -> Check configuration**.
7. Restart Home Assistant and perform a hard refresh in the browser or app.
8. Open **Jarvis** in the sidebar.

The animated voice card dispatches Home Assistant's standard Assist dashboard
action. It does not access the microphone directly and does not receive raw
audio. Keyboard activation and reduced-motion preferences are supported.

The dashboard uses the landscape theme. To use the portrait background for a
wall panel, change each view's `theme` from `Jarvis Command Center` to
`Jarvis Command Center Panel`.

## Entity mapping

The package is preconfigured for the accepted Project Jarvis test entities,
including `light.blocks`, the upstairs-office and interior-light groups,
`camera.porch_camera`, and `media_player.loftstue_group`.

If a tile reports that an entity is unavailable or does not exist, edit only
that card and select the matching entity from Home Assistant. The dashboard
does not alter entity permissions or device behavior.

## Update from 0.8.1

Replace `jarvis-dashboard.yaml`, the theme file, and
`www/jarvis/jarvis-voice-card.js`. Confirm that the JavaScript resource URL
ends in `?v=0.8.2`, restart Home Assistant, and hard-refresh the client.

## Remove

Remove the `jarvis-command-center` entry from the `lovelace.dashboards`
configuration, remove the Jarvis theme entry or file, and restart Home
Assistant. Existing dashboards and Project Jarvis memory are unaffected.
