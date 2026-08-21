from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from verbatim.config import Settings, get_settings
from verbatim.service import RagService, reset_service


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    """A configuration that needs no network, no API key and no model download."""
    monkeypatch.setenv("VERBATIM_EMBEDDING_PROVIDER", "hashing")
    monkeypatch.setenv("VERBATIM_VECTOR_STORE", "numpy")
    monkeypatch.setenv("VERBATIM_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("VERBATIM_MIN_SCORE", "0.0")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    reset_service()
    yield get_settings()
    get_settings.cache_clear()
    reset_service()


@pytest.fixture
def service(settings) -> RagService:
    return RagService(settings)


@pytest.fixture
def client(settings) -> TestClient:
    from verbatim.api.app import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def sample_markdown() -> bytes:
    return b"""# Leave policy

Employees accrue 20 days of paid annual leave per calendar year. Unused days
carry over to the following year up to a maximum of five.

# Expenses

Expenses must be submitted within 60 days using form EX-114. Receipts are
required for anything above 25 pounds.

# Equipment

Laptops are replaced on a three year cycle. Report a fault to the service desk
under reference SD-2200.
"""


@pytest.fixture
def upload(sample_markdown):
    def _upload(client: TestClient, name: str = "handbook.md", body: bytes | None = None):
        payload = body if body is not None else sample_markdown
        return client.post(
            "/api/documents", files={"file": (name, io.BytesIO(payload), "text/markdown")}
        )

    return _upload
