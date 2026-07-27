# M20 Voice Experience

Status: complete

## Outcome

Jarvis now supports a Home Assistant-owned voice path with an independently
selected microphone device, TTS provider, and media-player output. The initial
acceptance topology is the Home Assistant mobile app on `NSPanel Upstairs` as
input and `Loftstue Group` as output.

## Architecture

- Home Assistant owns microphone capture, speech-to-text, text-to-speech, and
  media playback.
- Jarvis receives text plus a bounded `voice_mode` flag. It does not receive or
  store raw audio.
- External output activates only when the incoming Home Assistant source device
  or its registered Assist satellite matches the selected microphone device.
- The custom integration calls Home Assistant's `tts.speak` action with the
  selected TTS entity and media player.
- Requests from other devices remain text/local responses.
- Typed Assist remains functional. Home Assistant does not expose text-versus-
  microphone modality to a conversation agent, so a typed request originating
  from the selected NSPanel device follows the same external-output route.
- When external playback succeeds, local pipeline speech is empty to prevent
  duplicate audio. If the selected speaker is unavailable or TTS fails, the
  normal local response is preserved.
- The full response remains in Home Assistant's conversation chat log.

## Spoken interaction

- Voice-mode model responses are limited to two short sentences unless the user
  requests detail.
- Friendly names and spoken units are preferred over entity identifiers.
- Common entity IDs and decimal-zero values are normalized for speech.
- Spoken output is bounded to 700 characters.
- Pending confirmations accept natural, session-bound answers including
  `yes`, `confirm`, `go ahead`, `no`, and `cancel`.
- A confirmation from another conversation cannot authorize or consume the
  pending request.

## Character

Jarvis uses an original calm, articulate, British-inspired presentation with
precise wording, restrained warmth, and optional subtle dry wit. M20 does not
clone a performer, reproduce film dialogue, or claim to be the fictional
character. The selected Home Assistant TTS provider determines the available
voice names and audio characteristics.

## Configuration

Configure the Project Jarvis Conversation integration options:

1. Enable external voice output.
2. Select `NSPanel Upstairs` as the microphone device.
3. Select `Loftstue Group` as the speaker or speaker group.
4. Select an installed TTS provider.
5. Choose the provider's language and optional voice name.
6. Keep duplicate-audio prevention enabled.

The integration validates the selected entities and availability of
`tts.speak`, then reloads itself after saving.

## Acceptance

- A request originating from the selected NSPanel device is spoken once through
  Loftstue Group.
- Typed Assist from a device other than the selected NSPanel does not speak
  through Loftstue Group.
- Unavailable external output falls back to the local/written response.
- Conversation identity and memory continuity are preserved.
- Natural yes/no confirmation is isolated to the originating conversation.
