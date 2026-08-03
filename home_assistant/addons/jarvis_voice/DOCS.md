# Project Jarvis Neural Voice

Project Jarvis Voice is a local Wyoming neural TTS service. Chatterbox Nano
generates an expressive voice on the Home Assistant CPU and streams the first
completed sentence while later sentences are generated. Bounded Jarvis
processing adds a restrained synthetic character. No cloud account is required.

## Installation

1. Keep the official **Piper** app installed as the optional fallback.
2. Install and start **Project Jarvis Voice** from the Project Jarvis app
   repository. The Chatterbox Nano and Kokoro models are included in the app image.
3. Add **Wyoming Protocol** under **Settings -> Devices & services** using the
   Home Assistant local IP and port `10350`.
4. Select **Project Jarvis Neural Voice** in the Jarvis Assist pipeline.

## Engines, voices, and profiles

The default `chatterbox_nano` engine uses `jarvis_neural`. Version 0.28.1 bundles
the approved Project Jarvis v5 reference as mono 24 kHz PCM. The project owner
retains the source permission record. The reference and resulting profile are
for this non-commercial open-source hobby project. Select `kokoro` to A/B test
the prior engine.

The default fallback voice is `bm_george`. You can also select `bm_fable`,
`bm_daniel`, or `bm_lewis` in Home Assistant.

- `jarvis_v5`: approved crisp, staccato and balanced synthetic/metallic finish.
- `refined`: restrained technical presence.
- `synthetic`: stronger resonance and doubling.
- `metallic`: raised pitch, controlled modulation, quantisation, and tight
  doubling; recommended when the neural base remains too human.
- `clean`: neural voice with minimal coloration.

`strength` controls the synthetic finishing layer and `output_gain` controls
the final level. The v5 default uses full calibrated strength, gain `0.98`, a
bounded delivery factor of `1.055`, and a `25` ms maximum long pause.
`staccato_pause_ms` may be set to `0` to disable PCM pause tightening. Restart
the app after changing options. If local neural
synthesis fails and `piper_fallback` is enabled, the request is sent to Piper.
`shorten_comma_pauses` removes the model's exaggerated comma timing while
preserving word separation.
`pitch_factor` raises pitch while slightly accelerating delivery. The v5
default is `1.055`; values above `1.14` will sound deliberately artificial.

Existing installations still using the untouched 0.27.2 Metallic defaults are
migrated in memory to v5. Explicitly customised profiles and levels are retained.

The model stays warm and synthesis is serialized. Logs report readiness,
time-to-first-audio, per-segment generation time, fallback state, and errors.
`generation_timeout` bounds each segment. If Chatterbox fails before audio
starts, Jarvis tries Kokoro; Piper remains the final fallback.

The service communicates only through Wyoming. It can later move to a separate
small-form-factor AI computer without moving Home Assistant or changing Jarvis's
language-model boundary.

## Privacy and boundaries

Generated reply PCM exists only in memory, is never written to disk, and is discarded after delivery. Home
Assistant owns Assist pipelines, TTS selection, devices, and audio routing.
Project Jarvis Voice cannot perform home actions.
