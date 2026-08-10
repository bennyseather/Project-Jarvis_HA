# M40 — Expanded Private Piper Voice

M40 replaces the M39 runtime default with a Piper medium model fine-tuned from
799 privately approved British English clips (approximately 79 minutes). The
model targets clear, low-latency CPU speech on the Home Assistant i5-8500 while
the existing bounded clarity processing remains available.

## Boundaries

- Source recordings, transcripts, caches, and checkpoints remain private.
- Git and the public add-on repository contain only runtime and training tools.
- The exported ONNX pair is transferred separately through Home Assistant share.
- Home Assistant owns Assist pipelines, TTS selection, and audio routing.

## Runtime and migration

The default engine is `piper_m40`, loading
`/share/jarvis_voice/jarvis-piper-m40.zip` into `/data/models/m40`. Untouched M39
defaults migrate automatically; explicitly customised package paths are kept.
The `piper_m39` engine remains selectable for immediate rollback.

The Wyoming voice is advertised as `jarvis_m40`. The model remains compatible
with later migration to a dedicated inference computer without moving Home
Assistant's entity, automation, or permission responsibilities.
