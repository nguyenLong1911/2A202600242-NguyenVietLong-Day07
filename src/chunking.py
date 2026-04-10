from __future__ import annotations

import math
import re


class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks


class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        # Keep sentence punctuation while splitting to preserve readability.
        sentences = [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", text.strip()) if piece.strip()]
        if not sentences:
            return [text.strip()]

        chunks: list[str] = []
        for index in range(0, len(sentences), self.max_sentences_per_chunk):
            grouped = sentences[index : index + self.max_sentences_per_chunk]
            chunks.append(" ".join(grouped).strip())
        return chunks


class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, separators: list[str] | None = None, chunk_size: int = 500) -> None:
        self.separators = self.DEFAULT_SEPARATORS if separators is None else list(separators)
        self.chunk_size = chunk_size

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []

        separators = self.separators if self.separators else [""]
        parts = self._split(text, separators)
        return [part.strip() for part in parts if part and part.strip()]

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:
        if len(current_text) <= self.chunk_size:
            return [current_text]

        if not remaining_separators:
            return [current_text[i : i + self.chunk_size] for i in range(0, len(current_text), self.chunk_size)]

        separator = remaining_separators[0]

        if separator == "":
            return [current_text[i : i + self.chunk_size] for i in range(0, len(current_text), self.chunk_size)]

        pieces = current_text.split(separator)
        if len(pieces) == 1:
            return self._split(current_text, remaining_separators[1:])

        chunks: list[str] = []
        buffer = ""
        for piece in pieces:
            candidate = piece if not buffer else buffer + separator + piece
            if len(candidate) <= self.chunk_size:
                buffer = candidate
                continue

            if buffer:
                chunks.extend(self._split(buffer, remaining_separators[1:]))
                buffer = ""

            if len(piece) <= self.chunk_size:
                buffer = piece
            else:
                chunks.extend(self._split(piece, remaining_separators[1:]))

        if buffer:
            chunks.extend(self._split(buffer, remaining_separators[1:]))

        return chunks


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    if not vec_a or not vec_b:
        return 0.0

    mag_a = math.sqrt(sum(value * value for value in vec_a))
    mag_b = math.sqrt(sum(value * value for value in vec_b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return _dot(vec_a, vec_b) / (mag_a * mag_b)


class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        fixed = FixedSizeChunker(chunk_size=chunk_size, overlap=min(50, max(0, chunk_size // 10))).chunk(text)
        by_sentences = SentenceChunker(max_sentences_per_chunk=max(1, chunk_size // 120 or 1)).chunk(text)
        recursive = RecursiveChunker(chunk_size=chunk_size).chunk(text)

        def _stats(chunks: list[str]) -> dict:
            count = len(chunks)
            avg_length = (sum(len(chunk) for chunk in chunks) / count) if count else 0.0
            return {
                "count": count,
                "avg_length": avg_length,
                "chunks": chunks,
            }

        return {
            "fixed_size": _stats(fixed),
            "by_sentences": _stats(by_sentences),
            "recursive": _stats(recursive),
        }
