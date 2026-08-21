from __future__ import annotations

import pytest

from verbatim.ingest.chunking import Chunker, _pack, _split_units
from verbatim.models import LoadedDocument, Segment


def make_document(text: str, **kwargs) -> LoadedDocument:
    return LoadedDocument(title="t", source_type="txt", segments=[Segment(text=text, **kwargs)])


def test_short_document_stays_one_chunk():
    chunks = Chunker(900, 150).split(make_document("A single short paragraph."), "d")
    assert len(chunks) == 1
    assert chunks[0].index == 0


def test_chunks_respect_the_size_budget():
    body = " ".join(f"Sentence number {i} carries a little filler text." for i in range(200))
    chunks = Chunker(400, 60).split(make_document(body), "d")
    assert len(chunks) > 1
    # The heading prefix is the only thing allowed to push a chunk over budget.
    assert all(len(c.text) <= 400 for c in chunks)


def test_overlap_repeats_content_between_neighbours():
    body = " ".join(f"Fact {i} about the system." for i in range(120))
    with_overlap = Chunker(300, 100).split(make_document(body), "d")
    without_overlap = Chunker(300, 0).split(make_document(body), "d")
    assert len(with_overlap) > len(without_overlap)


def test_boundaries_land_on_sentence_ends():
    body = " ".join(f"This is sentence {i} and it ends here." for i in range(80))
    for chunk in Chunker(300, 0).split(make_document(body), "d"):
        assert chunk.text.startswith("This is sentence")


def test_page_and_heading_survive_into_metadata():
    document = LoadedDocument(
        title="t",
        source_type="pdf",
        segments=[Segment(text="Body text about refunds.", page=7, heading="Refunds")],
    )
    chunk = Chunker(900, 100).split(document, "d")[0]
    assert chunk.page == 7
    assert chunk.heading == "Refunds"
    assert chunk.to_metadata("Doc")["page"] == 7
    assert chunk.text.startswith("Refunds")


def test_ids_are_stable_across_runs():
    document = make_document("Deterministic content for hashing.")
    first = Chunker(900, 100).split(document, "d")
    second = Chunker(900, 100).split(document, "d")
    assert [c.id for c in first] == [c.id for c in second]


def test_unsplittable_text_is_hard_cut():
    units = _split_units("x" * 250, 100)
    assert len(units) == 3
    assert all(len(u) <= 100 for u in units)


def test_pack_carries_the_tail_forward():
    packed = _pack(["alpha", "beta", "gamma", "delta"], size=12, overlap=6)
    assert len(packed) > 1
    assert "beta" in packed[0] and packed[1].startswith("beta")


def test_overlap_larger_than_chunk_is_rejected():
    with pytest.raises(ValueError):
        Chunker(200, 200)
