"""Train and export the private M40 Piper voice on a RunPod GPU Pod."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import wave
import zipfile


WORK = Path(os.environ.get("M40_WORKSPACE", "/workspace/jarvis-m40"))
ARCHIVE = Path(os.environ.get("M40_DATASET_ARCHIVE", WORK / "m40-piper-dataset.zip"))
REPO = WORK / "piper1-gpl"
DATASET = WORK / "m40-dataset"
OUTPUT = WORK / "jarvis-training"
CACHE = WORK / "jarvis-cache"
BASE = WORK / "en_GB_base.ckpt"
COMPAT = WORK / "en_GB_base_compat.ckpt"
BATCH_SIZE = int(os.environ.get("M40_BATCH_SIZE", "2"))
MAX_DURATION = float(os.environ.get("M40_MAX_DURATION", "10"))
MAX_TRANSCRIPT = int(os.environ.get("M40_MAX_TRANSCRIPT", "180"))


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def prepare_environment() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    run(["nvidia-smi"])
    run(["apt-get", "update", "-qq"])
    run(["apt-get", "install", "-y", "-qq", "build-essential", "cmake", "ninja-build"])
    if not REPO.exists():
        run([
            "git", "clone", "--branch", "v1.4.2", "--depth", "1",
            "https://github.com/OHF-Voice/piper1-gpl.git", str(REPO),
        ])
    pip = [sys.executable, "-m", "pip", "install", "--break-system-packages", "-q"]
    run([*pip, "scikit-build", "onnxscript"])
    run([*pip, "-e", ".[train]"], cwd=REPO)
    run(["bash", "build_monotonic_align.sh"], cwd=REPO)
    run([sys.executable, "setup.py", "build_ext", "--inplace"], cwd=REPO)
    assert any((REPO / "src/piper").glob("espeakbridge*.so")), "Piper espeakbridge build missing"


def prepare_dataset() -> tuple[Path, int, float]:
    assert ARCHIVE.exists(), f"Private dataset archive not found: {ARCHIVE}"
    shutil.rmtree(DATASET, ignore_errors=True)
    with zipfile.ZipFile(ARCHIVE) as bundle:
        bundle.extractall(DATASET)

    cards = list(DATASET.rglob("DATASET_CARD.json"))
    assert len(cards) == 1, f"Expected one DATASET_CARD.json, found {len(cards)}"
    dataset_root = cards[0].parent
    card = json.loads(cards[0].read_text(encoding="utf-8"))
    assert card["clip_count"] == 826
    assert len(list((dataset_root / "wav").glob("*.wav"))) == 826

    source_rows = (dataset_root / "metadata.csv").read_text(encoding="utf-8").splitlines()
    safe_rows: list[str] = []
    safe_seconds = 0.0
    for row in source_rows:
        fields = row.split("|")
        if len(fields) < 2:
            continue
        audio_name, transcript = fields[0], fields[1]
        audio_path = dataset_root / "wav" / (
            audio_name if audio_name.endswith(".wav") else f"{audio_name}.wav"
        )
        with wave.open(str(audio_path), "rb") as stream:
            duration = stream.getnframes() / stream.getframerate()
        if duration <= MAX_DURATION and len(transcript) <= MAX_TRANSCRIPT:
            safe_rows.append(row)
            safe_seconds += duration

    assert len(safe_rows) >= 700, f"Only {len(safe_rows)} bounded clips remain"
    metadata = dataset_root / "metadata-runpod.csv"
    metadata.write_text("\n".join(safe_rows) + "\n", encoding="utf-8")
    print(
        f"Dataset ready: {len(safe_rows)} clips, {safe_seconds:.2f} seconds "
        f"(limits: {MAX_DURATION}s/{MAX_TRANSCRIPT} chars)",
        flush=True,
    )
    return dataset_root, len(safe_rows), safe_seconds


def train(dataset_root: Path, clip_count: int) -> tuple[dict[str, str], Path]:
    import lightning.pytorch.cli as lightning_cli
    import torch

    OUTPUT.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    if not BASE.exists():
        urllib.request.urlretrieve(
            "https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/main/"
            "en/en_GB/northern_english_male/medium/epoch%3D9029-step%3D2261720.ckpt?download=true",
            BASE,
        )

    checkpoint = torch.load(BASE, weights_only=False, map_location="cpu")
    checkpoint["hyper_parameters"] = {}
    checkpoint["epoch"] = 0
    checkpoint["global_step"] = 0
    progress_keys = {"ready", "started", "processed", "completed"}

    def reset_progress(value: object) -> None:
        if isinstance(value, dict):
            for key, child in list(value.items()):
                if key in progress_keys and isinstance(child, int):
                    value[key] = 0
                else:
                    reset_progress(child)
        elif isinstance(value, list):
            for child in value:
                reset_progress(child)

    reset_progress(checkpoint.get("loops", {}))
    torch.save(checkpoint, COMPAT)

    cli_path = Path(lightning_cli.__file__)
    cli_text = cli_path.read_text(encoding="utf-8")
    old_load = 'torch.load(ckpt_path, weights_only=True, map_location="cpu")'
    trusted_load = 'torch.load(ckpt_path, weights_only=False, map_location="cpu")'
    assert old_load in cli_text or trusted_load in cli_text
    if old_load in cli_text:
        cli_path.write_text(cli_text.replace(old_load, trusted_load, 1), encoding="utf-8")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO / "src")
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    command = [
        sys.executable, "-u", "-m", "piper.train", "fit",
        "--data.voice_name", "jarvis",
        "--data.csv_path", str(dataset_root / "metadata-runpod.csv"),
        "--data.audio_dir", str(dataset_root / "wav"),
        "--model.sample_rate", "22050",
        "--data.espeak_voice", "en",
        "--data.cache_dir", str(CACHE),
        "--data.config_path", str(OUTPUT / "en_GB-jarvis-medium.onnx.json"),
        "--data.batch_size", str(BATCH_SIZE),
        "--ckpt_path", str(COMPAT),
        "--trainer.accelerator", "gpu",
        "--trainer.devices", "1",
        "--trainer.precision", "16-mixed",
        "--trainer.max_epochs", "60",
        "--trainer.default_root_dir", str(OUTPUT),
        "--weights_only", "true",
    ]
    print(f"Starting 60 epochs with {clip_count} clips at batch size {BATCH_SIZE}", flush=True)
    run(command, cwd=REPO, env=environment)
    return environment, OUTPUT


def export(environment: dict[str, str], output: Path) -> Path:
    checkpoints = sorted(output.rglob("*.ckpt"), key=lambda path: path.stat().st_mtime)
    assert checkpoints, "Training produced no checkpoint"
    latest = checkpoints[-1]
    model = output / "en_GB-jarvis-medium.onnx"
    config = output / "en_GB-jarvis-medium.onnx.json"
    export_source = REPO / "src/piper/train/export_onnx.py"
    export_text = export_source.read_text(encoding="utf-8")
    legacy_axes = "        dynamic_axes={"
    legacy_export = "        dynamo=False,\n        dynamic_axes={"
    assert legacy_axes in export_text or legacy_export in export_text
    if legacy_export not in export_text:
        export_source.write_text(export_text.replace(legacy_axes, legacy_export, 1), encoding="utf-8")
    run([
        sys.executable, "-m", "piper.train.export_onnx",
        "--checkpoint", str(latest), "--output-file", str(model),
    ], cwd=REPO, env=environment)

    package = WORK / "jarvis-piper-m40.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(model, model.name)
        bundle.write(config, config.name)
    print(f"M40_EXPORT_READY={package}", flush=True)
    return package


def main() -> None:
    prepare_environment()
    dataset_root, clip_count, _ = prepare_dataset()
    environment, output = train(dataset_root, clip_count)
    export(environment, output)


if __name__ == "__main__":
    main()
