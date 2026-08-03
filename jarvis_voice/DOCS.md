# Project Jarvis Neural Voice

Project Jarvis Voice is a local Wyoming neural TTS service. Kokoro-82M creates
the British voice on the Home Assistant CPU, then bounded Jarvis processing
adds a restrained synthetic character. No cloud TTS account is required.

## Installation

1. Keep the official **Piper** app installed as the optional fallback.
2. Install and start **Project Jarvis Voice** from the Project Jarvis app
   repository. The neural model is included in the app image.
3. Add **Wyoming Protocol** under **Settings -> Devices & services** using the
   Home Assistant local IP and port `10350`.
4. Select **Project Jarvis Neural Voice** in the Jarvis Assist pipeline.

## Voices and profiles

The default voice is `bm_george`. You can also select `bm_fable`, `bm_daniel`,
or `bm_lewis` in Home Assistant. The tuned default uses speed `1.08`.

- `refined`: restrained technical presence.
- `synthetic`: stronger resonance and doubling.
- `metallic`: raised pitch, controlled modulation, quantisation, and tight
  doubling; recommended when the neural base remains too human.
- `clean`: neural voice with minimal coloration.

`strength` controls the synthetic finishing layer and `output_gain` controls
the final level. Restart the app after changing options. If local neural
synthesis fails and `piper_fallback` is enabled, the request is sent to Piper.
`shorten_comma_pauses` removes the model's exaggerated comma timing while
preserving word separation.
`pitch_factor` raises pitch while slightly accelerating delivery. Start at
`1.10`; values above `1.14` will sound deliberately artificial.

## Privacy and boundaries

Generated PCM exists only in memory, is never written to disk, and is discarded after delivery. Home
Assistant owns Assist pipelines, TTS selection, devices, and audio routing.
Project Jarvis Voice cannot perform home actions.
