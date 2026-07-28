# D1 Jarvis Command Center

Status: complete

## Outcome

Project Jarvis includes an optional, responsive Home Assistant dashboard and
theme with original visual assets, a direct Assist launcher, known home
controls, voice routing guidance, and privacy-safe administration links.

## Architecture

- Home Assistant owns dashboard rendering, entity state, and actions.
- Jarvis core does not render or persist frontend state.
- The UI pack uses built-in Home Assistant cards and theme variables.
- No HACS or third-party frontend dependency is required.
- Installation is explicit because the Jarvis add-on is not granted write
  access to Home Assistant's `/config` directory.
- Existing dashboards, device permissions, memories, and conversation
  behavior are unchanged.

## Views

1. Command
2. Rooms
3. Environment
4. Media & Voice
5. Jarvis

## Visual system

- Deep graphite and navy surfaces.
- Muted cyan primary accents and restrained amber attention accents.
- High-contrast text and responsive Sections layouts.
- Original abstract technical backgrounds without copyrighted logos,
  characters, performers, or film imagery.

## Packaging

The installable files are in `home_assistant/jarvis_ui`. The corresponding
Home Assistant release repository publishes them under `jarvis_ui`.
