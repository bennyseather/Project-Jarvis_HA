"""Minimal Wyoming JSONL and PCM framing used by the voice proxy."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    header: dict
    data: dict
    payload: bytes = b""

    @property
    def type(self) -> str:
        return str(self.header.get("type", ""))


async def read_event(reader: asyncio.StreamReader) -> Event | None:
    line = await reader.readline()
    if not line:
        return None
    header = json.loads(line.decode("utf-8"))
    data_bytes = await reader.readexactly(int(header.get("data_length", 0)))
    payload = await reader.readexactly(int(header.get("payload_length", 0)))
    header.pop("data_length", None)
    header.pop("payload_length", None)
    data = dict(header.pop("data", {}))
    if data_bytes:
        data.update(json.loads(data_bytes.decode("utf-8")))
    return Event(header=header, data=data, payload=payload)


async def write_event(writer: asyncio.StreamWriter, event: Event) -> None:
    header = dict(event.header)
    data = dict(header.pop("data", {}))
    data.update(event.data)
    data_bytes = json.dumps(data, separators=(",", ":")).encode("utf-8") if data else b""
    if data_bytes:
        header["data_length"] = len(data_bytes)
    else:
        header.pop("data_length", None)
    if event.payload:
        header["payload_length"] = len(event.payload)
    else:
        header.pop("payload_length", None)
    writer.write(
        json.dumps(header, separators=(",", ":")).encode("utf-8") + b"\n"
    )
    if data_bytes:
        writer.write(data_bytes)
    if event.payload:
        writer.write(event.payload)
    await writer.drain()
