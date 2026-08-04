"""Package only manually accepted M39 clips for private GPU training."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile


def package(dataset: Path, output: Path) -> dict:
    review_path = dataset / "review.csv"
    with review_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    pending = [row for row in rows if row["review_status"] == "needs_review"]
    if pending:
        raise ValueError(f"Dataset still has {len(pending)} pending reviews")
    accepted = [row for row in rows if row["review_status"] == "accepted"]
    if not accepted:
        raise ValueError("Dataset has no accepted clips")
    card = {
        "name": "Project Jarvis M39 private voice dataset",
        "clip_count": len(accepted),
        "duration_seconds": round(sum(float(row["duration"]) for row in accepted), 3),
        "sample_rate": 22050,
        "speaker_count": 1,
        "manual_review_complete": True,
        "redistribution": False,
        "clips": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        metadata_lines = []
        for row in accepted:
            audio_path = dataset / "wav" / row["file"]
            payload = audio_path.read_bytes()
            archive.writestr(f"wav/{row['file']}", payload)
            metadata_lines.append(f"{row['file']}|{row['text'].strip()}")
            card["clips"].append({
                "file": row["file"],
                "duration": float(row["duration"]),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
        archive.writestr("metadata.csv", "\n".join(metadata_lines) + "\n")
        archive.writestr("DATASET_CARD.json", json.dumps(card, indent=2))
    return card


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(package(arguments.dataset, arguments.output), indent=2))


if __name__ == "__main__":
    main()
