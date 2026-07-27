"""Pure voice-routing policy and spoken-response formatting."""

from __future__ import annotations

import re

from .const import (
    CONF_EXTERNAL_VOICE_OUTPUT,
    CONF_INPUT_DEVICE_ID,
    CONF_OUTPUT_MEDIA_PLAYER,
    CONF_SUPPRESS_LOCAL_AUDIO,
    CONF_TTS_ENTITY,
    CONF_TTS_LANGUAGE,
    CONF_TTS_VOICE,
    DEFAULT_TTS_LANGUAGE,
)


def should_route_external(options, device_id: str | None) -> bool:
    """Route only configured requests originating from the selected device."""
    return bool(
        options.get(CONF_EXTERNAL_VOICE_OUTPUT, False)
        and device_id
        and device_id == options.get(CONF_INPUT_DEVICE_ID)
        and options.get(CONF_OUTPUT_MEDIA_PLAYER)
        and options.get(CONF_TTS_ENTITY)
    )


def build_tts_service_data(options, message: str) -> dict[str, object]:
    """Build the exact Home Assistant tts.speak payload."""
    data: dict[str, object] = {
        "entity_id": options[CONF_TTS_ENTITY],
        "media_player_entity_id": options[CONF_OUTPUT_MEDIA_PLAYER],
        "message": format_spoken_response(message),
        "cache": True,
    }
    if language := options.get(CONF_TTS_LANGUAGE, DEFAULT_TTS_LANGUAGE).strip():
        data["language"] = language
    if voice := options.get(CONF_TTS_VOICE, "").strip():
        data["options"] = {"voice": voice}
    return data


def suppress_local_audio(options) -> bool:
    return bool(options.get(CONF_SUPPRESS_LOCAL_AUDIO, True))


def format_spoken_response(message: str, maximum_characters: int = 700) -> str:
    """Make a transcript response comfortable to hear without changing meaning."""
    text = " ".join(message.replace(";", ",").split())
    text = re.sub(r"\b(-?\d+)\.0\b", r"\1", text)
    text = re.sub(
        r"\b(?:light|switch|sensor|binary_sensor|media_player)\.([a-z0-9_]+)\b",
        lambda match: match.group(1).replace("_", " "),
        text,
        flags=re.IGNORECASE,
    )
    if len(text) <= maximum_characters:
        return text
    shortened = text[:maximum_characters].rsplit(" ", 1)[0].rstrip(" ,;:")
    return shortened + "."
