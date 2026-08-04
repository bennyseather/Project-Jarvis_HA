# M39 — Dedicated Jarvis Piper Voice

M39 replaces the default CPU-heavy Chatterbox path with a dedicated Piper
medium model fine-tuned from the privately approved Xeno recordings. The model
is exported to ONNX for fast CPU inference on the current Home Assistant i5-8500.

## Boundaries

- The recordings, reviewed dataset, checkpoints and exported model remain private.
- Git and the public add-on repository contain only the loader and training tools.
- Home Assistant owns the Assist pipeline and audio routing.
- Jarvis Voice performs TTS only and cannot execute home actions.

## Runtime

The add-on reads `/share/jarvis_voice/jarvis-piper-m39.zip`, validates and
extracts the ONNX pair into its private `/data` directory, then serves the
`jarvis_m39` voice over Wyoming. The existing Jarvis DSP adds bounded darkness,
metallic character, short pauses and final gain. Kokoro and the official Piper
service remain local fallbacks.

The target is 1–4 seconds to first audio for normal replies. Logs expose model
readiness, synthesis time and fallback errors. The model location is configurable
so it can later move to a dedicated small-form-factor AI host without changing
Home Assistant's authority boundary.
