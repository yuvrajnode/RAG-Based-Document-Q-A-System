"""Chunking.

Retrieval quality is decided here more than anywhere else in the pipeline. Two
rules drive the implementation:

1. Never split in the middle of a sentence if a paragraph break is available.
   A chunk that starts mid-clause embeds badly and reads worse when it is
   quoted back to the user as a citation.
2. Keep the structural context (page, nearest heading) attached to the chunk.
   It costs a few bytes of metadata and buys precise citations.

The splitter walks a ladder of separators - paragraph, line, sentence, word -
and only drops to the next rung when a piece is still too large.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from verbatim.models import Chunk, LoadedDocument, Segment, stable_id

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")
_SEPARATORS: tuple[str, ...] = ("\n\n", "\n")


@dataclass(slots=True)
class _Block:
    text: str
    page: int | None
    heading: str | None


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_END.split(text)
    return [p for p in (part.strip() for part in parts) if p]


def _split_units(text: str, limit: int) -> list[str]:
    """Break text into pieces that are each <= limit where the text allows it."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    for separator in _SEPARATORS:
        if separator not in text:
            continue
        pieces = [p for p in text.split(separator) if p.strip()]
        if len(pieces) == 1:
            continue
        units: list[str] = []
        for piece in pieces:
            if len(piece) <= limit:
                units.append(piece)
                continue
            sentences = _split_sentences(piece)
            if len(sentences) > 1:
                for sentence in sentences:
                    units.extend(_split_units(sentence, limit))
            else:
                units.extend(_split_units(piece, limit))
        return units

    # One long paragraph: fall back to sentences, then to words. Sentences are
    # tried first so a chunk boundary lands on a full stop where it can.
    sentences = _split_sentences(text)
    if len(sentences) > 1:
        units: list[str] = []
        for sentence in sentences:
            units.extend(_split_units(sentence, limit))
        return units

    words = text.split(" ")
    if len(words) > 1:
        units, buffer = [], ""
        for word in words:
            candidate = f"{buffer} {word}".strip()
            if buffer and len(candidate) > limit:
                units.append(buffer)
                buffer = word
            else:
                buffer = candidate
        if buffer:
            units.append(buffer)
        return units

    # A URL, a base64 blob, or a script we do not tokenise. Hard-cut it.
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _pack(units: list[str], size: int, overlap: int) -> list[str]:
    """Greedily fill chunks to `size`, carrying `overlap` characters forward."""
    chunks: list[str] = []
    buffer: list[str] = []
    length = 0

    for unit in units:
        addition = len(unit) + (1 if buffer else 0)
        if buffer and length + addition > size:
            chunks.append(" ".join(buffer))
            if overlap > 0:
                tail: list[str] = []
                tail_length = 0
                for previous in reversed(buffer):
                    if tail_length + len(previous) > overlap:
                        break
                    tail.insert(0, previous)
                    tail_length += len(previous) + 1
                buffer = tail
                length = tail_length
            else:
                buffer, length = [], 0
            addition = len(unit) + (1 if buffer else 0)
        buffer.append(unit)
        length += addition

    if buffer:
        chunks.append(" ".join(buffer))
    return chunks


class Chunker:
    def __init__(self, chunk_size: int = 900, chunk_overlap: int = 150, min_chars: int = 80):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chars = min_chars

    def _blocks(self, segments: list[Segment]) -> list[_Block]:
        """Merge neighbouring segments that share a heading and still fit."""
        blocks: list[_Block] = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            if blocks:
                last = blocks[-1]
                same_context = last.heading == segment.heading and last.page == segment.page
                if same_context and len(last.text) + len(text) + 2 <= self.chunk_size:
                    last.text = f"{last.text}\n\n{text}"
                    continue
            blocks.append(_Block(text=text, page=segment.page, heading=segment.heading))
        return blocks

    def split(self, document: LoadedDocument, document_id: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        cursor = 0
        index = 0

        for block in self._blocks(document.segments):
            units = _split_units(block.text, self.chunk_size)
            for body in _pack(units, self.chunk_size, self.chunk_overlap):
                body = body.strip()
                if not body:
                    continue
                # A stub shorter than min_chars is usually a stray caption. Fold
                # it into the previous chunk rather than polluting the index.
                if len(body) < self.min_chars and chunks:
                    previous = chunks[-1]
                    if previous.page == block.page:
                        previous.text = f"{previous.text} {body}"
                        previous.char_end += len(body) + 1
                        cursor += len(body) + 1
                        continue

                heading = block.heading
                text = f"{heading}\n\n{body}" if heading and not body.startswith(heading) else body
                chunks.append(
                    Chunk(
                        id=stable_id(document_id, index, body[:256]),
                        document_id=document_id,
                        text=text,
                        index=index,
                        page=block.page,
                        heading=heading,
                        char_start=cursor,
                        char_end=cursor + len(body),
                    )
                )
                cursor += len(body) + 1
                index += 1

        return chunks


def chunk_document(
    document: LoadedDocument,
    document_id: str,
    *,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
) -> list[Chunk]:
    return Chunker(chunk_size, chunk_overlap).split(document, document_id)
