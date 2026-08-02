# M31 - Voice Activation and Wake-Word Routing

Release: 0.21.2

## Architecture

Home Assistant remains the sole owner of microphones, wake-word detection,
speech-to-text, text-to-speech, Assist pipelines, devices, and speaker routing.
Jarvis receives only the resulting text, conversation identity, source identity,
and an activation identifier. Jarvis stores no audio.

The optional `jarvis-voice-satellite-card` is a development satellite for a
Windows browser. It uses the signed-in Home Assistant WebSocket connection,
captures mono browser audio only after explicit permission, uses a local
energy gate, resamples speech to 16 kHz PCM, and streams it to
`assist_pipeline/run`. It supports Home
Assistant/openWakeWord activation and push-to-talk, preserves the returned
conversation ID, plays pipeline TTS through the browser, and releases the
microphone immediately when muted or removed.

## Safety and reliability

- A bounded activation-result cache prevents a repeated wake activation from
  executing the same request twice. Its key includes conversation and source.
- Confirmations remain bound to the originating conversation.
- Pipeline errors are visible on the card and never trigger home actions by
  themselves.
- The card does not request a long-lived access token and stores no audio.
- Wake listening is opt-in per open browser card and always exposes mute.

## Scope exclusions

This milestone does not add continuous server-side recording, voice biometrics,
speaker recognition, a proprietary wake-word engine, or a second STT/TTS stack.
Production room satellites remain Home Assistant Assist satellites.

## Acceptance

Use Home Assistant over HTTPS on the Windows development PC. Add the Jarvis
Voice Satellite card, permit microphone access, verify push-to-talk and wake
word commands, confirm TTS returns through the PC speakers, mute the card, and
verify the browser microphone indicator switches off.
