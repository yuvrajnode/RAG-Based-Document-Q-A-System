"""Anthropic client wrapper.

Kept deliberately thin: one place that knows about the SDK, so the answer
engine can be tested without it and the extractive fallback can stand in when
no API key is configured.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from verbatim.logging import get_logger

log = get_logger(__name__)


class LLMUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class Completion:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ClaudeClient:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ):
        if not api_key:
            raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable("the anthropic package is not installed") from exc

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def complete(self, system: str, prompt: str) -> Completion:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return Completion(
            text=text.strip(),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            yield from stream.text_stream
