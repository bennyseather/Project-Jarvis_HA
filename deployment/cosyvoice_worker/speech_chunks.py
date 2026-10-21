"""Lossless, bounded text segmentation; no model or audio dependencies."""
import re


def speech_chunks(text: str, chunk_limit: int = 320, total_limit: int = 12000):
    text = " ".join(text.split())
    if len(text) > total_limit:
        raise ValueError("Speech exceeds the utterance limit; refusing to truncate it")
    limit = max(80, min(chunk_limit or 320, 2000))
    if any(len(word) > limit for word in text.split()):
        raise ValueError("Speech contains a token longer than the chunk limit")
    chunks = []
    while len(text) > limit:
        candidates = [m.start()+1 for m in re.finditer(r"[.!?;:,](?=\s|$)", text)]
        before = [n for n in candidates if n <= limit]
        boundary = before[-1] if before else next((n for n in candidates if n > limit), len(text))
        if boundary > 2000:
            raise ValueError("Speech clause exceeds the complete-section limit; refusing to split mid-sentence")
        chunks.append(text[:boundary].strip())
        text = text[boundary:].strip()
    if text:
        chunks.append(text)
    return chunks
