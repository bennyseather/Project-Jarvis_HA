"""Bounded, deterministic PCM effects for an original synthetic voice."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
import sys


@dataclass(frozen=True)
class Profile:
    high_pass_hz: float
    presence: float
    compression_threshold: float
    compression_ratio: float
    resonance: float
    resonance_ms: float
    doubling: float
    doubling_ms: float
    modulation_depth: float = 0.0
    modulation_hz: float = 0.0
    quantization_steps: int = 0


PROFILES = {
    "clean": Profile(65.0, 0.04, 0.72, 1.8, 0.0, 0.0, 0.0, 0.0),
    "refined": Profile(82.0, 0.14, 0.48, 2.8, 0.075, 6.5, 0.045, 13.0),
    "synthetic": Profile(95.0, 0.22, 0.42, 3.4, 0.14, 5.0, 0.09, 11.0),
    "metallic": Profile(
        125.0, 0.34, 0.34, 4.2, 0.22, 3.7, 0.16, 7.5,
        modulation_depth=0.16, modulation_hz=71.0, quantization_steps=1024,
    ),
}


JARVIS_V5_SYNTHETIC_MIX = 0.20
JARVIS_V5_METALLIC_MIX = 0.61


def process_voice_pcm16(
    pcm: bytes,
    sample_rate: int,
    channels: int,
    profile_name: str,
    strength: float,
    output_gain: float,
    staccato_pause_ms: float = 0.0,
) -> bytes:
    """Apply one named finishing chain with a calibrated Jarvis v5 option."""
    if not pcm or channels != 1 or sample_rate < 8000:
        return pcm
    if profile_name != "jarvis_v5":
        return process_pcm16(
            pcm, sample_rate, channels, profile_name, strength, output_gain
        )
    pcm = tighten_pauses_pcm16(
        pcm,
        sample_rate,
        maximum_pause_ms=staccato_pause_ms,
    )
    bounded_strength = max(0.0, min(1.0, float(strength)))
    pcm = process_pcm16(
        pcm,
        sample_rate,
        channels,
        "synthetic",
        JARVIS_V5_SYNTHETIC_MIX * bounded_strength,
        1.02,
    )
    return process_pcm16(
        pcm,
        sample_rate,
        channels,
        "metallic",
        JARVIS_V5_METALLIC_MIX * bounded_strength,
        output_gain,
    )


def tighten_pauses_pcm16(
    pcm: bytes,
    sample_rate: int,
    *,
    maximum_pause_ms: float,
    minimum_silence_ms: float = 100.0,
    threshold: float = 0.01,
) -> bytes:
    """Shorten long digital-silence runs while preserving speech boundaries."""
    maximum_pause_ms = max(0.0, min(250.0, float(maximum_pause_ms)))
    if not pcm or maximum_pause_ms <= 0.0 or sample_rate < 8000:
        return pcm
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    maximum_pause = round(sample_rate * maximum_pause_ms / 1000.0)
    minimum_silence = max(
        maximum_pause + 1,
        round(sample_rate * minimum_silence_ms / 1000.0),
    )
    silence_limit = max(1, round(32767.0 * max(0.0, min(0.2, threshold))))
    output = array("h")
    run_start = 0
    index = 0
    while index < len(samples):
        if abs(samples[index]) > silence_limit:
            output.append(samples[index])
            index += 1
            continue
        run_start = index
        while index < len(samples) and abs(samples[index]) <= silence_limit:
            index += 1
        run_length = index - run_start
        if run_length < minimum_silence:
            output.extend(samples[run_start:index])
            continue
        keep = min(run_length, maximum_pause)
        leading = keep // 2
        trailing = keep - leading
        output.extend(samples[run_start:run_start + leading])
        output.extend(samples[index - trailing:index])
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


def process_pcm16(
    pcm: bytes,
    sample_rate: int,
    channels: int,
    profile_name: str,
    strength: float,
    output_gain: float,
) -> bytes:
    """Process signed little-endian PCM16 without retaining audio."""
    if not pcm or channels != 1 or sample_rate < 8000:
        return pcm
    profile = PROFILES.get(profile_name, PROFILES["metallic"])
    mix = max(0.0, min(1.0, float(strength)))
    gain = max(0.25, min(1.5, float(output_gain)))
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    dry = [value / 32768.0 for value in samples]
    wet = _effect(dry, sample_rate, profile)
    output = array("h")
    for original, processed in zip(dry, wet):
        value = (original * (1.0 - mix) + processed * mix) * gain
        value = math.tanh(value * 1.08) / math.tanh(1.08)
        output.append(max(-32768, min(32767, round(value * 32767.0))))
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


def _effect(samples: list[float], rate: int, profile: Profile) -> list[float]:
    rc = 1.0 / (2.0 * math.pi * profile.high_pass_hz)
    dt = 1.0 / rate
    alpha = rc / (rc + dt)
    high_passed: list[float] = []
    previous_input = previous_output = 0.0
    for value in samples:
        filtered = alpha * (previous_output + value - previous_input)
        previous_input, previous_output = value, filtered
        high_passed.append(filtered)

    resonance_delay = max(1, round(rate * profile.resonance_ms / 1000.0))
    doubling_delay = max(1, round(rate * profile.doubling_ms / 1000.0))
    output: list[float] = []
    previous = 0.0
    for index, value in enumerate(high_passed):
        presence = value + profile.presence * (value - previous)
        previous = value
        if profile.resonance and index >= resonance_delay:
            presence += profile.resonance * high_passed[index - resonance_delay]
        if profile.doubling and index >= doubling_delay:
            presence -= profile.doubling * high_passed[index - doubling_delay]
        magnitude = abs(presence)
        threshold = profile.compression_threshold
        if magnitude > threshold:
            magnitude = threshold + (magnitude - threshold) / profile.compression_ratio
            presence = math.copysign(magnitude, presence)
        if profile.modulation_depth:
            carrier = math.sin(2.0 * math.pi * profile.modulation_hz * index / rate)
            presence *= 1.0 - profile.modulation_depth + profile.modulation_depth * carrier
        if profile.quantization_steps:
            presence = round(presence * profile.quantization_steps) / profile.quantization_steps
        output.append(presence)
    return output


def raise_pitch_and_speed_pcm16(pcm: bytes, factor: float) -> bytes:
    """Raise pitch and shorten delivery with bounded linear resampling."""
    factor = max(1.0, min(1.2, float(factor)))
    if not pcm or factor == 1.0:
        return pcm
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    output_count = max(1, int(len(samples) / factor))
    output = array("h")
    for index in range(output_count):
        position = index * factor
        left = min(len(samples) - 1, int(position))
        right = min(len(samples) - 1, left + 1)
        fraction = position - left
        output.append(round(samples[left] * (1.0 - fraction) + samples[right] * fraction))
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()
