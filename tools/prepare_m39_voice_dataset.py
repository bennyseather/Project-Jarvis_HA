"""Prepare a reviewable Piper dataset from approved long-form voice recordings."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from scipy.signal import resample_poly
import soundfile as sf


TARGET_RATE = 22050
MIN_SECONDS = 1.2
MAX_SECONDS = 12.0


def clean_transcript(text: str) -> str:
    """Normalize whitespace while retaining spoken punctuation and casing."""
    return re.sub(r"\s+", " ", text).strip()


def bounded_windows(segment, maximum: float = MAX_SECONDS):
    """Split a Whisper segment at word boundaries without inventing text."""
    words = list(segment.words or ())
    if not words or segment.end - segment.start <= maximum:
        yield float(segment.start), float(segment.end), clean_transcript(segment.text)
        return
    current = []
    started = float(words[0].start)
    for word in words:
        if current and float(word.end) - started > maximum:
            yield started, float(current[-1].end), clean_transcript(
                "".join(item.word for item in current)
            )
            current = []
            started = float(word.start)
        current.append(word)
    if current:
        yield started, float(current[-1].end), clean_transcript(
            "".join(item.word for item in current)
        )


def audio_metrics(samples: np.ndarray) -> dict[str, float | int]:
    """Return deterministic QA metrics without retaining source audio."""
    absolute = np.abs(samples)
    peak = float(absolute.max(initial=0.0))
    rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
    clipping = int(np.count_nonzero(absolute >= 0.999))
    return {
        "peak": round(peak, 6),
        "rms_dbfs": round(20.0 * math.log10(max(rms, 1e-9)), 2),
        "clipped_samples": clipping,
    }


def normalize_clip(samples: np.ndarray) -> np.ndarray:
    """Peak-normalize clean speech conservatively without synthetic effects."""
    peak = float(np.abs(samples).max(initial=0.0))
    if peak <= 1e-6:
        return samples.astype(np.float32)
    gain = min(1.5, (10.0 ** (-3.0 / 20.0)) / peak)
    return np.clip(samples * gain, -1.0, 1.0).astype(np.float32)


def prepare(sources: list[Path], output: Path, model_name: str) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    audio_dir = output / "wav"
    audio_dir.mkdir(exist_ok=True)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    rows = []
    source_rows = []
    for source_index, source in enumerate(sources, start=1):
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        decoded = decode_audio(str(source), sampling_rate=16000)
        source_rows.append({
            "name": source.name,
            "sha256": source_hash,
            "duration_seconds": round(len(decoded) / 16000.0, 3),
        })
        segments, info = model.transcribe(
            str(source), language="en", beam_size=5, vad_filter=True,
            word_timestamps=True, condition_on_previous_text=False,
        )
        clip_index = 0
        for segment in segments:
            for start, end, transcript in bounded_windows(segment):
                duration = end - start
                if duration < MIN_SECONDS or not transcript:
                    continue
                clip_index += 1
                margin = 0.10
                first = max(0, round((start - margin) * 16000))
                last = min(len(decoded), round((end + margin) * 16000))
                clip_16k = decoded[first:last].astype(np.float32)
                clip = resample_poly(clip_16k, 441, 320).astype(np.float32)
                before = audio_metrics(clip)
                clip = normalize_clip(clip)
                identifier = f"xeno{source_index}_{clip_index:04d}"
                filename = f"{identifier}.wav"
                sf.write(audio_dir / filename, clip, TARGET_RATE, subtype="PCM_16")
                rows.append({
                    "id": identifier,
                    "file": filename,
                    "text": transcript,
                    "source": source.name,
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "duration": round(len(clip) / TARGET_RATE, 3),
                    "language_probability": round(float(info.language_probability), 4),
                    **before,
                    "review_status": "needs_review",
                })
    with (output / "metadata.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="|")
        for row in rows:
            writer.writerow((row["file"], row["text"]))
    with (output / "review.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["id"])
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "model": model_name,
        "target_rate": TARGET_RATE,
        "sources": source_rows,
        "clip_count": len(rows),
        "usable_seconds_before_manual_review": round(sum(row["duration"] for row in rows), 3),
        "clipping_flag_count": sum(row["clipped_samples"] > 0 for row in rows),
        "review_required": True,
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="small.en")
    arguments = parser.parse_args()
    print(json.dumps(prepare(arguments.sources, arguments.output, arguments.model), indent=2))


if __name__ == "__main__":
    main()
