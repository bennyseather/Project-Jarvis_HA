# M41 - Qwen Jarvis Voice Runtime

## Outcome

Project Jarvis uses a private, warm Qwen3-TTS 1.7B worker for its approved voice
while Home Assistant remains isolated on its dedicated computer. The existing
Jarvis Wyoming proxy owns routing and presentation filters; it cannot perform
home actions.

## Architecture

`Home Assistant Assist -> Jarvis Voice proxy -> private Qwen worker -> PCM`

- The Qwen worker runs on an NVIDIA GPU and caches model and clone conditioning.
- The winning 8.88-second reference and exact transcript are mounted read-only.
- Clean audio streams as soon as Qwen completes the first bounded sentence.
- Optional `refined`, `synthesized`, `synthetic`, and `metallic` post-filters
  remain in the Jarvis proxy and never alter the source model.
- Local Kokoro and configured Piper remain automatic failure fallbacks.
- Moving the worker from RunPod to a future local AI computer only changes
  `qwen_host`; the Home Assistant pipeline remains unchanged.

## Boundaries

The worker accepts text and returns audio only. It has no Home Assistant token,
entity access, memory access, orchestration authority, or action capability.
Private voice assets and caches are excluded from Git and public releases.

## Performance target

Warm RTX 4090 evaluation produced 4.0 seconds of audio in 2.9 seconds and 7.8
seconds in 5.0 seconds. The clean streaming route avoids whole-response proxy
buffering. Filtered responses trade first-audio latency for click-free whole-
segment processing.
