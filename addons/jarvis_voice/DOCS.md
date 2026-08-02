# Project Jarvis Voice

Project Jarvis Voice is a local Wyoming TTS processor for the existing Piper
app. It creates an original British synthetic assistant sound without cloning
an actor, using cloud processing, or retaining generated audio.

## Prerequisites

Install and start the official Piper app first. Select a British Piper voice;
`en_GB-alan-medium` is recommended.

## Installation

1. Install and start **Project Jarvis Voice** from the Project Jarvis app
   repository.
2. Keep `upstream_host` set to `core-piper` and `upstream_port` to `10200`.
   If the log reports a DNS error, open the Piper app's **Info** page and use
   its displayed hostname instead.
3. Go to **Settings -> Devices & services -> Add integration** and select
   **Wyoming Protocol**.
4. Enter host `homeassistant.local` and port `10350`. The port is exposed only
   on your Home Assistant host; do not forward it through your router.
5. Rename the discovered TTS service to **Jarvis Piper**.
6. Open **Settings -> Voice assistants -> Jarvis** and choose the new Piper
   TTS service. Select `en_GB-alan-medium`.

## Profiles

- `refined`: restrained British technical voice; recommended.
- `synthetic`: stronger resonance and doubling.
- `clean`: light cleanup and compression with minimal coloration.

`strength` blends the processed signal with the original Piper signal.
`output_gain` adjusts the final level before a soft limiter. Start with the
defaults. Restart the app after changing options.

Normal Piper remains installed and selectable as an immediate bypass.

## Privacy and boundaries

Only the generated PCM response exists briefly in memory while it is being
processed. It is discarded after delivery and never written to disk. Home
Assistant continues to own Assist pipelines, TTS selection, devices, and audio
routing. Project Jarvis Voice cannot perform home actions.
