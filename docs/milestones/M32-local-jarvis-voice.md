# M32 - Local Jarvis Voice Refinement

Release: 0.22.0

## Architecture

Project Jarvis Voice is a Wyoming TTS proxy between Home Assistant and the
official local Piper app. Home Assistant owns the Assist pipeline, TTS entity,
satellites, and audio routing. Piper generates the British voice. The proxy
holds one generated PCM response in memory, applies bounded deterministic DSP,
returns the transformed Wyoming stream, and discards the buffer.

## Profiles

- Refined: restrained resonance, articulation, compression, and light doubling.
- Synthetic: a stronger but still intelligible technical treatment.
- Clean: minimal high-pass filtering and compression.

Strength and final gain are explicit bounded app options. Direct Piper remains
available as a bypass and operational fallback.

## Boundaries

The milestone does not clone an actor, train on proprietary recordings, retain
audio, use cloud TTS, alter Home Assistant permissions, or perform home actions.
The voice is an original British synthetic identity inspired by the general
category of cinematic technical assistants, not a reproduction of a character
or performance.
