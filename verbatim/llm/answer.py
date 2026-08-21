"""Answer synthesis: retrieve, ground, cite."""

from __future__ import annotations

import re
import time
from collections.abc import Iterator

from verbatim.llm.client import ClaudeClient, LLMUnavailable
from verbatim.llm.prompts import NO_CONTEXT_REPLY, SYSTEM_PROMPT, build_user_prompt
from verbatim.logging import get_logger
from verbatim.models import Answer, Citation, RetrievedChunk
from verbatim.retrieval.retriever import Retriever

log = get_logger(__name__)

_MARKER = re.compile(r"\[(\d{1,2})\]")
_SNIPPET_CHARS = 280


def _snippet(text: str) -> str:
    body = " ".join(text.split())
    if len(body) <= _SNIPPET_CHARS:
        return body
    cut = body[:_SNIPPET_CHARS]
    stop = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[: stop + 1] if stop > 160 else cut).rstrip() + "..."


def extract_citations(text: str, chunks: list[RetrievedChunk]) -> list[Citation]:
    """Resolve the markers the model actually used, in order of first use.

    Markers that point past the end of the context are dropped rather than
    trusted - it is rare, but a dangling [7] rendered as a real source is
    exactly the kind of thing that erodes confidence in the whole answer.
    """
    citations: list[Citation] = []
    seen: set[int] = set()
    for match in _MARKER.finditer(text):
        marker = int(match.group(1))
        if marker in seen or not 1 <= marker <= len(chunks):
            continue
        seen.add(marker)
        chunk = chunks[marker - 1]
        citations.append(
            Citation(
                marker=marker,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                page=chunk.page,
                snippet=_snippet(chunk.text),
            )
        )
    return sorted(citations, key=lambda c: c.marker)


def _extractive_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """What we return when no API key is configured.

    No synthesis, no paraphrase - just the passages that matched, labelled. It
    is a worse product than a generated answer, but it is honest about what it
    is and it keeps the retrieval half of the system demonstrable on its own.
    """
    lines = [
        "No language model is configured, so here are the passages that best match "
        "the question, ranked. Set ANTHROPIC_API_KEY to get a synthesised answer.",
        "",
    ]
    for index, chunk in enumerate(chunks, start=1):
        where = f", page {chunk.page}" if chunk.page is not None else ""
        lines.append(f"**{chunk.document_title}{where}** [{index}]")
        lines.append(_snippet(chunk.text))
        lines.append("")
    return "\n".join(lines).strip()


class AnswerEngine:
    def __init__(self, retriever: Retriever, client: ClaudeClient | None, model_name: str):
        self.retriever = retriever
        self.client = client
        self.model_name = model_name if client else "extractive-fallback"

    @property
    def generative(self) -> bool:
        return self.client is not None

    def _retrieve(self, question: str, top_k: int | None, document_ids: list[str] | None):
        return self.retriever.retrieve(question, top_k=top_k, document_ids=document_ids)

    def answer(
        self,
        question: str,
        *,
        top_k: int | None = None,
        document_ids: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> Answer:
        started = time.perf_counter()
        retrieval = self._retrieve(question, top_k, document_ids)

        if not retrieval.chunks:
            return Answer(
                question=question,
                text=NO_CONTEXT_REPLY,
                citations=[],
                contexts=[],
                model=self.model_name,
                latency_ms=self._elapsed(started),
                grounded=False,
            )

        if self.client is None:
            text = _extractive_answer(question, retrieval.chunks)
        else:
            prompt = build_user_prompt(question, retrieval.chunks, history)
            try:
                text = self.client.complete(SYSTEM_PROMPT, prompt).text
            except Exception as exc:
                log.exception("generation failed, falling back to extractive output")
                text = f"_Generation failed ({exc.__class__.__name__}); showing raw passages._\n\n"
                text += _extractive_answer(question, retrieval.chunks)

        citations = extract_citations(text, retrieval.chunks)
        return Answer(
            question=question,
            text=text,
            citations=citations,
            contexts=retrieval.chunks,
            model=self.model_name,
            latency_ms=self._elapsed(started),
            grounded=bool(citations),
        )

    def stream(
        self,
        question: str,
        *,
        top_k: int | None = None,
        document_ids: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> Iterator[tuple[str, object]]:
        """Yields (event, payload) pairs: sources first, then token deltas, then done.

        Sending sources before the first token is what lets the UI render the
        citation panel while the answer is still being written.
        """
        started = time.perf_counter()
        retrieval = self._retrieve(question, top_k, document_ids)
        yield "sources", [chunk.as_dict() for chunk in retrieval.chunks]

        if not retrieval.chunks:
            yield "delta", NO_CONTEXT_REPLY
            yield "done", {"citations": [], "latency_ms": self._elapsed(started), "grounded": False}
            return

        if self.client is None:
            text = _extractive_answer(question, retrieval.chunks)
            yield "delta", text
        else:
            prompt = build_user_prompt(question, retrieval.chunks, history)
            collected: list[str] = []
            try:
                for piece in self.client.stream(SYSTEM_PROMPT, prompt):
                    collected.append(piece)
                    yield "delta", piece
            except Exception as exc:
                log.exception("streaming generation failed")
                yield "error", str(exc)
                if not collected:
                    text = _extractive_answer(question, retrieval.chunks)
                    yield "delta", text
                    collected.append(text)
            text = "".join(collected)

        citations = extract_citations(text, retrieval.chunks)
        yield "done", {
            "citations": [c.as_dict() for c in citations],
            "latency_ms": self._elapsed(started),
            "retrieval_ms": retrieval.took_ms,
            "strategy": retrieval.strategy,
            "grounded": bool(citations),
        }

    @staticmethod
    def _elapsed(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)


def create_client(settings) -> ClaudeClient | None:
    if not settings.llm_enabled:
        log.warning("ANTHROPIC_API_KEY is not set - answers will be extractive only")
        return None
    try:
        return ClaudeClient(
            settings.anthropic_api_key,
            settings.llm_model,
            settings.llm_max_tokens,
            settings.llm_temperature,
        )
    except LLMUnavailable as exc:
        log.warning("%s - answers will be extractive only", exc)
        return None
