# M33 - Conversational Voice Sessions

Release: 0.24.0

The browser Jarvis Voice Satellite keeps a bounded dialogue window open after
TTS playback. Follow-ups reuse Home Assistant's conversation identifier and
Assist pipeline without requiring the wake word again. The default window is
seven seconds with at most three follow-up turns.

Silence, explicit exit phrases, pipeline errors, mute, card removal, or the
turn limit return the satellite to wake-word mode. Playback completes before
the follow-up microphone path opens, preventing Jarvis from hearing itself.
Audio remains transient and Home Assistant continues to own microphone access,
STT, TTS, pipelines, and device routing.
