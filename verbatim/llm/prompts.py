"""Prompt construction.

The whole point of the system is that answers are traceable, so the prompt is
built around two constraints: the model may only use the supplied passages, and
every claim carries the marker of the passage it came from. Refusing is an
acceptable outcome and is stated as such - a model that is not allowed to say
"the documents do not cover this" will invent something instead.
"""

from __future__ import annotations

from verbatim.models import RetrievedChunk

SYSTEM_PROMPT = """\
You are a research assistant answering questions strictly from a set of \
retrieved passages taken from the user's own documents.

Rules:
1. Use only the passages provided. Do not add outside knowledge, and do not \
guess at anything the passages leave unstated.
2. Cite with square-bracket markers that match the passage numbers, e.g. [2]. \
Every sentence containing a fact must carry at least one marker. Cite multiple \
passages as [1][3] when a claim draws on more than one.
3. If the passages do not contain the answer, say so plainly in one sentence \
and name what is missing. Do not pad the response with related material.
4. Quote exact figures, dates, names and identifiers as they appear. Do not \
round or rephrase them.
5. Answer in prose. Use a short bulleted list only when the question asks for \
several discrete items. Keep it under 200 words unless the question genuinely \
needs more.

Write in a neutral, factual register. No preamble such as "Based on the \
provided passages" - go straight to the answer."""

_PASSAGE_TEMPLATE = """[{marker}] {title}{location}
{text}"""


def _location(chunk: RetrievedChunk) -> str:
    parts = []
    if chunk.page is not None:
        parts.append(f"page {chunk.page}")
    if chunk.heading:
        parts.append(chunk.heading)
    return f" ({', '.join(parts)})" if parts else ""


def format_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        _PASSAGE_TEMPLATE.format(
            marker=index, title=chunk.document_title, location=_location(chunk), text=chunk.text
        )
        for index, chunk in enumerate(chunks, start=1)
    )


def build_user_prompt(question: str, chunks: list[RetrievedChunk], history: list[dict] | None = None) -> str:
    sections = []
    if history:
        # Only the last few turns; older context competes with the passages for
        # the model's attention and rarely earns its tokens.
        turns = "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in history[-4:])
        sections.append(f"Earlier in this conversation:\n{turns}")
    sections.append(f"Passages:\n\n{format_context(chunks)}")
    sections.append(f"Question: {question}")
    return "\n\n---\n\n".join(sections)


NO_CONTEXT_REPLY = (
    "I could not find anything relevant in the indexed documents. "
    "Try rephrasing the question, or upload a document that covers it."
)
