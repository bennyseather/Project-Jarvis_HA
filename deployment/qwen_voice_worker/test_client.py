"""Small Wyoming client for deployment acceptance testing."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import time
import wave

from protocol import Event, read_event, write_event


async def run(host: str, port: int, text: str, output: Path) -> None:
    reader, writer = await asyncio.open_connection(host, port)
    started = time.monotonic()
    await write_event(writer, Event({"type": "synthesize"}, {
        "text": text, "voice": {"name": "jarvis_qwen"},
    }))
    metadata = None
    chunks: list[bytes] = []
    first_audio = None
    while event := await read_event(reader):
        if event.type == "audio-start":
            metadata = event.data
            first_audio = time.monotonic() - started
        elif event.type == "audio-chunk":
            chunks.append(event.payload)
        elif event.type == "audio-stop":
            break
    writer.close()
    await writer.wait_closed()
    if metadata is None or first_audio is None:
        raise RuntimeError("Worker returned no audio")
    with wave.open(str(output), "wb") as audio:
        audio.setnchannels(int(metadata["channels"]))
        audio.setsampwidth(int(metadata["width"]))
        audio.setframerate(int(metadata["rate"]))
        audio.writeframes(b"".join(chunks))
    print({
        "first_audio_seconds": round(first_audio, 3),
        "complete_seconds": round(time.monotonic() - started, 3),
        "output": str(output),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10400)
    parser.add_argument("--text", default="Certainly, Benny. All systems are operating normally.")
    parser.add_argument("--output", type=Path, default=Path("qwen-worker-test.wav"))
    arguments = parser.parse_args()
    asyncio.run(run(arguments.host, arguments.port, arguments.text, arguments.output))
