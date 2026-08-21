from __future__ import annotations

import pytest

from verbatim.llm.answer import AnswerEngine, extract_citations
from verbatim.llm.prompts import build_user_prompt, format_context
from verbatim.models import RetrievedChunk


def chunk(index: int, title: str = "Handbook", page: int | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"c{index}",
        document_id="d",
        document_title=title,
        text=f"Passage number {index} with enough text to be worth citing.",
        score=1.0 - index / 10,
        page=page,
    )


class StubClient:
    """Stands in for the Anthropic client; records what it was asked."""

    model = "stub"

    def __init__(self, reply: str = "The leave allowance is 20 days [1]."):
        self.reply = reply
        self.system: str | None = None
        self.prompt: str | None = None

    def complete(self, system, prompt):
        from verbatim.llm.client import Completion

        self.system, self.prompt = system, prompt
        return Completion(text=self.reply, model=self.model)

    def stream(self, system, prompt):
        self.system, self.prompt = system, prompt
        yield from self.reply.split(" ")


class StubRetriever:
    def __init__(self, chunks):
        self._chunks = chunks

    def retrieve(self, query, top_k=None, document_ids=None):
        from verbatim.retrieval.retriever import RetrievalResult

        return RetrievalResult(self._chunks, 1, len(self._chunks), 0, "stub")


# --- citations ------------------------------------------------------------
def test_markers_resolve_to_the_matching_passages():
    citations = extract_citations("Fact one [1]. Fact two [3].", [chunk(i) for i in range(1, 4)])
    assert [c.marker for c in citations] == [1, 3]
    assert citations[0].chunk_id == "c1"


def test_repeated_markers_are_reported_once():
    citations = extract_citations("A [1]. B [1]. C [1].", [chunk(1)])
    assert len(citations) == 1


def test_markers_past_the_end_of_the_context_are_dropped():
    assert extract_citations("Claim [9].", [chunk(1)]) == []


def test_text_without_markers_yields_no_citations():
    assert extract_citations("A confident answer with no sources.", [chunk(1)]) == []


def test_snippets_are_truncated_for_display():
    long_chunk = chunk(1)
    long_chunk.text = "word " * 400
    assert len(extract_citations("x [1]", [long_chunk])[0].snippet) <= 285


# --- prompts --------------------------------------------------------------
def test_context_is_numbered_from_one_and_carries_the_page():
    rendered = format_context([chunk(1, page=4), chunk(2)])
    assert rendered.startswith("[1] Handbook (page 4)")
    assert "[2] Handbook\n" in rendered


def test_history_is_trimmed_to_the_recent_turns():
    history = [{"role": "user", "content": f"turn {i}"} for i in range(10)]
    prompt = build_user_prompt("Question?", [chunk(1)], history)
    assert "turn 9" in prompt and "turn 3" not in prompt


# --- engine ---------------------------------------------------------------
def test_answer_returns_text_and_resolved_citations():
    engine = AnswerEngine(StubRetriever([chunk(1), chunk(2)]), StubClient(), "stub")
    answer = engine.answer("How much leave?")
    assert answer.grounded is True
    assert answer.citations[0].marker == 1
    assert len(answer.contexts) == 2


def test_empty_retrieval_refuses_instead_of_answering():
    engine = AnswerEngine(StubRetriever([]), StubClient(), "stub")
    answer = engine.answer("Anything at all?")
    assert answer.grounded is False
    assert answer.citations == []
    assert "could not find" in answer.text


def test_a_generation_failure_degrades_to_the_passages():
    class Broken(StubClient):
        def complete(self, system, prompt):
            raise RuntimeError("upstream 503")

    engine = AnswerEngine(StubRetriever([chunk(1)]), Broken(), "stub")
    answer = engine.answer("Question?")
    assert "Generation failed" in answer.text
    assert "Passage number 1" in answer.text


def test_without_a_client_the_engine_is_extractive():
    engine = AnswerEngine(StubRetriever([chunk(1)]), None, "stub")
    assert engine.generative is False
    assert engine.answer("Question?").model == "extractive-fallback"


def test_stream_emits_sources_first_then_deltas_then_done():
    engine = AnswerEngine(StubRetriever([chunk(1)]), StubClient(), "stub")
    events = list(engine.stream("Question?"))
    assert events[0][0] == "sources"
    assert events[-1][0] == "done"
    assert "".join(payload for name, payload in events if name == "delta").strip()
    assert events[-1][1]["grounded"] is True


@pytest.mark.parametrize("reply", ["", "No markers here."])
def test_ungrounded_replies_are_flagged(reply):
    engine = AnswerEngine(StubRetriever([chunk(1)]), StubClient(reply), "stub")
    assert engine.answer("Question?").grounded is False
