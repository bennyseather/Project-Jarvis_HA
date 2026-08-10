"""Private Project Jarvis Piper voice loaded from shared storage."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
import subprocess
import zipfile


LOGGER = logging.getLogger("jarvis_voice.private_piper")
MODEL_NAME = "en_GB-jarvis-medium.onnx"
CONFIG_NAME = f"{MODEL_NAME}.json"


@dataclass(frozen=True)
class PiperM39Config:
    package_path: str = "/share/jarvis_voice/jarvis-piper-m39.zip"
    cache_dir: str = "/data/models/m39"
    executable: str = "piper"
    timeout: float = 20.0
    noise_scale: float = 0.35
    noise_w: float = 0.45


class PiperM39Engine:
    def __init__(self, config: PiperM39Config) -> None:
        self.config = config
        self._lock = asyncio.Lock()
        self._model_path: Path | None = None
        self._config_path: Path | None = None
        self.last_error = ""
        self.last_generation_seconds = 0.0

    @property
    def ready(self) -> bool:
        return self._model_path is not None and self._config_path is not None

    async def prepare(self) -> None:
        await asyncio.to_thread(self._prepare_sync)

    def _prepare_sync(self) -> None:
        package = Path(self.config.package_path)
        if not package.is_file():
            raise FileNotFoundError(
                f"Private voice package not found at {package}; copy the configured model ZIP to /share/jarvis_voice"
            )
        destination = Path(self.config.cache_dir)
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package) as archive:
            names = {entry.filename for entry in archive.infolist() if not entry.is_dir()}
            required = {MODEL_NAME, CONFIG_NAME}
            if not required.issubset(names):
                raise ValueError(f"M39 package is missing: {sorted(required - names)}")
            for name in required:
                target = destination / name
                with archive.open(name) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
        model = destination / MODEL_NAME
        config = destination / CONFIG_NAME
        if model.stat().st_size < 1_000_000 or config.stat().st_size < 100:
            raise ValueError("Private voice package contains invalid model files")
        self._model_path = model
        self._config_path = config
        self.last_error = ""
        LOGGER.info("Private Piper model ready: %.1f MB", model.stat().st_size / 1_000_000)

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        if not self.ready:
            await self.prepare()
        async with self._lock:
            return await asyncio.wait_for(
                asyncio.to_thread(self._synthesize_sync, text), self.config.timeout
            )

    def _synthesize_sync(self, text: str) -> tuple[bytes, int]:
        if self._model_path is None or self._config_path is None:
            raise RuntimeError("M39 Piper model is not prepared")
        import time

        started = time.monotonic()
        result = subprocess.run(
            [
                self.config.executable,
                "--model", str(self._model_path),
                "--config", str(self._config_path),
                "--noise-scale", str(max(0.0, min(1.0, self.config.noise_scale))),
                "--noise-w", str(max(0.0, min(1.0, self.config.noise_w))),
                "--output-raw",
            ],
            input=(text.strip() + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=self.config.timeout,
        )
        if result.returncode != 0 or not result.stdout:
            detail = result.stderr.decode("utf-8", errors="replace").strip()[-500:]
            self.last_error = detail or f"Piper exited with {result.returncode}"
            raise RuntimeError(self.last_error)
        self.last_generation_seconds = time.monotonic() - started
        self.last_error = ""
        return result.stdout, 22050
