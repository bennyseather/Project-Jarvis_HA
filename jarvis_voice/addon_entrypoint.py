"""Home Assistant add-on entry point for the local Jarvis voice processor."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from server import VoiceProxyConfig, run_server


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def load_config(path: Path = Path("/data/options.json")) -> VoiceProxyConfig:
    options = json.loads(path.read_text(encoding="utf-8"))
    source_engine = str(options.get("engine", "qwen_1_7b"))
    legacy_defaults = (
        int(options.get("voice_revision", 0)) < 5
        and str(options.get("profile", "metallic")) == "metallic"
        and float(options.get("strength", 0.92)) == 0.92
        and float(options.get("output_gain", 0.92)) == 0.92
        and float(options.get("pitch_factor", 1.10)) == 1.10
    )
    v5_defaults = (
        int(options.get("voice_revision", 5)) < 6
        and str(options.get("profile", "jarvis_v5")) == "jarvis_v5"
        and float(options.get("pitch_factor", 1.055)) == 1.055
    )
    m39_defaults = (
        int(options.get("voice_revision", 6)) < 7
        and source_engine == "chatterbox_nano"
        and str(options.get("profile", "jarvis_v5")) == "jarvis_v5"
        and float(options.get("strength", 1.0)) == 1.0
        and float(options.get("output_gain", 0.98)) == 0.98
        and float(options.get("pitch_factor", 1.035)) == 1.035
    )
    m40_defaults = (
        int(options.get("voice_revision", 7)) < 8
        and source_engine == "piper_m39"
        and str(options.get("model_package", "/share/jarvis_voice/jarvis-piper-m39.zip"))
        == "/share/jarvis_voice/jarvis-piper-m39.zip"
        and str(options.get("model_cache_dir", "/data/models/m39")) == "/data/models/m39"
    )
    m42_defaults = (
        int(options.get("voice_revision", 8)) < 9
        and source_engine == "qwen_1_7b"
        and float(options.get("generation_timeout", 30.0)) == 30.0
    )
    latency_defaults = (
        int(options.get("voice_revision", 9)) < 10
        and source_engine == "qwen_1_7b"
        and int(options.get("qwen_maximum_spoken_characters", 420)) == 420
        and bool(options.get("qwen_buffer_before_playback", True))
    )
    complete_speech_defaults = (
        int(options.get("voice_revision", 10)) < 11
        and source_engine == "qwen_1_7b"
        and int(options.get("qwen_maximum_spoken_characters", 260)) in {260, 420}
    )
    engine = "piper_m40" if m40_defaults else "piper_m39" if m39_defaults else source_engine
    return VoiceProxyConfig(
        upstream_host=str(options.get("upstream_host", "core-piper")),
        upstream_port=int(options.get("upstream_port", 10200)),
        model_package=(
            "/share/jarvis_voice/jarvis-piper-m40.zip"
            if m40_defaults else str(options.get(
                "model_package", "/share/jarvis_voice/jarvis-piper-m40.zip"
            ))
        ),
        model_cache_dir=(
            "/data/models/m40" if m40_defaults
            else str(options.get("model_cache_dir", "/data/models/m40"))
        ),
        profile=(
            "jarvis_v5" if legacy_defaults
            else str(options.get("profile", "jarvis_v5"))
        ),
        strength=(
            1.0 if legacy_defaults else float(options.get("strength", 1.0))
        ),
        output_gain=(
            0.98 if legacy_defaults else float(options.get("output_gain", 0.98))
        ),
        voice=str(options.get("voice", "bm_george")),
        speed=float(options.get("speed", 1.08)),
        shorten_comma_pauses=bool(options.get("shorten_comma_pauses", True)),
        pitch_factor=(
            1.055 if legacy_defaults
            else 1.035 if v5_defaults
            else float(options.get("pitch_factor", 1.035))
        ),
        staccato_pause_ms=float(options.get("staccato_pause_ms", 25.0)),
        darkness=float(options.get(
            "darkness",
            0.12 if (
                engine in {"piper_m39", "piper_m40"}
                or int(options.get("voice_revision", 0)) >= 7
            ) else 0.10,
        )),
        piper_fallback=bool(options.get("piper_fallback", True)),
        engine=engine,
        reference_path=str(options.get("reference_path", "/app/jarvis-reference.wav")),
        generation_timeout=(
            300.0 if m42_defaults
            else float(options.get("generation_timeout", 300.0))
        ),
        warm_model=bool(options.get("warm_model", True)),
        articulation_mode=str(options.get("articulation_mode", "crisp")),
        maximum_segment_characters=int(
            options.get("maximum_segment_characters", 105)
        ),
        piper_noise_scale=float(options.get("piper_noise_scale", 0.35)),
        piper_noise_w=float(options.get("piper_noise_w", 0.45)),
        clarity_mode=bool(options.get("clarity_mode", True)),
        qwen_host=str(options.get("qwen_host", "127.0.0.1")),
        qwen_port=int(options.get("qwen_port", 10400)),
        qwen_filter=str(options.get("qwen_filter", "clean")),
        qwen_filter_strength=float(options.get("qwen_filter_strength", 0.55)),
        qwen_connect_timeout=float(options.get("qwen_connect_timeout", 3.0)),
        qwen_maximum_spoken_characters=int(
            4000 if complete_speech_defaults else options.get(
                "qwen_maximum_spoken_characters", 4000
            )
        ),
        qwen_buffer_before_playback=bool(
            False if latency_defaults else options.get("qwen_buffer_before_playback", False)
        ),
        qwen_maximum_buffer_bytes=int(
            options.get("qwen_maximum_buffer_megabytes", 64)
        ) * 1024 * 1024,
    )


if __name__ == "__main__":
    asyncio.run(run_server(load_config()))
