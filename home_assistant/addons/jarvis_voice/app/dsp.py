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


PROFILES = {
    "clean": Profile(65.0, 0.04, 0.72, 1.8, 0.0, 0.0, 0.0, 0.0),
    "refined": Profile(82.0, 0.14, 0.48, 2.8, 0.075, 6.5, 0.045, 13.0),
    "synthetic": Profile(95.0, 0.22, 0.42, 3.4, 0.14, 5.0, 0.09, 11.0),
}


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
    profile = PROFILES.get(profile_name, PROFILES["refined"])
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
        output.append(presence)
    return output
