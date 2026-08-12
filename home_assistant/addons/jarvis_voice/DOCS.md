# Project Jarvis Qwen Voice

Version 0.32.0 adds M41's private Qwen3-TTS 1.7B worker route. The worker runs
on a GPU computer, while this lightweight add-on remains on Home Assistant and
continues to expose the same Wyoming service on port `10350`.

Set `engine: qwen_1_7b`, `qwen_host` to the worker's private LAN/VPN address,
and `qwen_port: 10400`. Use `qwen_filter: clean` to preserve the approved clone.
The optional `synthesized` filter adds restrained electronic resonance and
articulation without bit crushing; `metallic` is intentionally stronger.
Adjust `qwen_filter_strength` from `0.0` to `1.0`.

For the temporary CPU worker, retain `generation_timeout: 300`. The
`qwen_maximum_spoken_characters` option defaults to 420 and bounds unusually
long TTS payloads at a sentence boundary. Qwen remains primary throughout the
timeout; fallback voices are used only when Qwen genuinely fails.

The Qwen worker, installation instructions, and example Docker Compose file are
in `deployment/qwen_voice_worker`. Never expose its unauthenticated Wyoming port
to the public internet. The private reference audio and transcript are mounted
on the worker and are never distributed through Git, HACS, or the add-on image.

# Previous dedicated Piper voice

Version 0.31.0 introduces the M40 model trained from the expanded, privately
approved British voice dataset. It retains `clarity_mode` by default. This lowers
Piper inference randomness, attenuates high-frequency model hiss, and bypasses
the synthetic finishing chain for an unambiguous model-quality baseline. Set
`clarity_mode: false` to restore the configured Jarvis DSP profile.

Project Jarvis Voice is a local Wyoming TTS service. M40 defaults to a private
Piper medium model trained for Jarvis, with bounded synthetic finishing and no
cloud account or per-request cost.

## Installation

1. Keep the official **Piper** app installed as the optional fallback.
2. Create `/share/jarvis_voice` and copy `jarvis-piper-m40.zip` into it without
   extracting the archive.
3. Install or update **Project Jarvis Voice** from the Project Jarvis app repository.
4. Add **Wyoming Protocol** under **Settings -> Devices & services** using the
   Home Assistant local IP and port `10350`.
5. Select **Jarvis M40** in the Jarvis Assist pipeline.

## Engines, voices, and profiles

The default `piper_m40` engine uses `jarvis_m40`. The private model ZIP is loaded
from `/share` and is never included in Git or the public app image. The previous
`piper_m39` engine remains available for rollback. Chatterbox
Nano and Kokoro remain fallback/A-B engines. Version 0.29.0 bundles
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
bounded delivery factor of `1.035`, a restrained darkness value of `0.10`, and
a `25` ms maximum long pause.
`staccato_pause_ms` may be set to `0` to disable PCM pause tightening. Restart
the app after changing options. If local neural
synthesis fails and `piper_fallback` is enabled, the request is sent to Piper.
`shorten_comma_pauses` removes the model's exaggerated comma timing while
preserving word separation.
`pitch_factor` raises pitch while slightly accelerating delivery. The darker
M38 v5 default is `1.035`; values above `1.14` sound deliberately artificial.

M38 prepares and caches reference conditioning once during startup, then runs a
short discarded pre-warm phrase before the Wyoming service reports ready.
`articulation_mode: crisp` uses conservative generation parameters to reduce
slurring. `balanced` retains more variation. `maximum_segment_characters`
defaults to `105`; Jarvis protects decimals and common abbreviations while
preferring sentence and clause boundaries. Values between `90` and `120` are
recommended on the i5-8500.

Existing installations still using the untouched 0.27.2 Metallic defaults are
migrated in memory to v5. Explicitly customised profiles and levels are retained.

The model stays warm and synthesis is serialized. Logs report conditioning and
warm-up time, time-to-first-audio, per-segment generation, fallback state, and errors.
`generation_timeout` bounds each segment. If Chatterbox fails before audio
starts, Jarvis tries Kokoro; Piper remains the final fallback.

The service communicates only through Wyoming. It can later move to a separate
small-form-factor AI computer without moving Home Assistant or changing Jarvis's
language-model boundary.

## Privacy and boundaries

Generated reply PCM exists only in memory, is never written to disk, and is discarded after delivery. Home
Assistant owns Assist pipelines, TTS selection, devices, and audio routing.
Project Jarvis Voice cannot perform home actions.
