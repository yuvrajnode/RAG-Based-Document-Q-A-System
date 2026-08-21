from __future__ import annotations

import io
import json


def test_health_reports_an_empty_index_on_a_fresh_install(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["documents"] == 0
    assert body["generative"] is False  # no API key in the test environment


def test_upload_indexes_a_document(client, upload):
    response = upload(client)
    assert response.status_code == 201
    body = response.json()
    assert body["document"]["chunk_count"] > 0
    assert body["replaced"] is False
    assert client.get("/api/health").json()["documents"] == 1


def test_reuploading_identical_content_replaces_rather_than_duplicates(client, upload):
    first = upload(client).json()
    second = upload(client, name="handbook-copy.md").json()
    assert second["document"]["id"] == first["document"]["id"]
    assert second["replaced"] is True
    assert client.get("/api/documents").json()["documents"].__len__() == 1


def test_unsupported_file_type_is_rejected(client):
    response = client.post(
        "/api/documents",
        files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert response.status_code == 415


def test_empty_upload_is_rejected(client):
    response = client.post(
        "/api/documents", files={"file": ("blank.txt", io.BytesIO(b""), "text/plain")}
    )
    assert response.status_code == 400


def test_upload_over_the_size_limit_is_rejected(client, monkeypatch):
    from verbatim.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0.0001)
    response = client.post(
        "/api/documents", files={"file": ("big.txt", io.BytesIO(b"x" * 5000), "text/plain")}
    )
    assert response.status_code == 413


def test_batch_upload_reports_partial_success(client, sample_markdown):
    response = client.post(
        "/api/documents/batch",
        files=[
            ("files", ("good.md", io.BytesIO(sample_markdown), "text/markdown")),
            ("files", ("bad.exe", io.BytesIO(b"MZ"), "application/octet-stream")),
        ],
    )
    body = response.json()
    assert len(body["ingested"]) == 1
    assert body["failed"][0]["filename"] == "bad.exe"


def test_search_returns_scored_passages(client, upload):
    upload(client)
    body = client.post("/api/search", json={"query": "how do I claim expenses"}).json()
    assert body["results"]
    assert "EX-114" in " ".join(result["text"] for result in body["results"])
    assert body["took_ms"] >= 0


def test_search_can_be_scoped_to_one_document(client, upload):
    document_id = upload(client).json()["document"]["id"]
    assert client.post(
        "/api/search", json={"query": "leave", "document_ids": [document_id]}
    ).json()["results"]
    assert (
        client.post("/api/search", json={"query": "leave", "document_ids": ["nope"]}).json()[
            "results"
        ]
        == []
    )


def test_ask_returns_an_answer_with_sources(client, upload):
    upload(client)
    body = client.post("/api/ask", json={"question": "How many days of annual leave?"}).json()
    assert body["sources"]
    assert body["model"] == "extractive-fallback"
    assert body["latency_ms"] >= 0


def test_ask_on_an_empty_index_refuses(client):
    body = client.post("/api/ask", json={"question": "Anything?"}).json()
    assert body["grounded"] is False
    assert body["sources"] == []


def test_ask_validates_the_question(client):
    assert client.post("/api/ask", json={"question": " "}).status_code == 422
    assert client.post("/api/ask", json={"question": "ok", "top_k": 99}).status_code == 422


def test_ask_stream_emits_server_sent_events(client, upload):
    upload(client)
    with client.stream(
        "POST", "/api/ask/stream", json={"question": "What is form EX-114?"}
    ) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        payload = b"".join(response.iter_bytes()).decode()

    events = [
        line.removeprefix("event: ") for line in payload.split("\n") if line.startswith("event: ")
    ]
    assert events[0] == "sources"
    assert events[-1] == "done"

    first_data = payload.split("data: ", 1)[1].split("\n", 1)[0]
    assert isinstance(json.loads(first_data), list)


def test_delete_removes_the_document_and_its_chunks(client, upload):
    document_id = upload(client).json()["document"]["id"]
    assert client.delete(f"/api/documents/{document_id}").status_code == 204
    assert client.get("/api/health").json()["chunks"] == 0
    assert client.delete(f"/api/documents/{document_id}").status_code == 404


def test_clear_empties_the_index(client, upload):
    upload(client)
    assert client.delete("/api/documents").status_code == 204
    assert client.get("/api/documents").json()["documents"] == []


def test_stats_describes_the_running_configuration(client):
    body = client.get("/api/stats").json()
    assert body["vector_store"] == "numpy"
    assert body["embedding"]["provider"].startswith("hashing")
    assert body["retrieval"]["top_k"] >= 1


def test_responses_carry_a_timing_header(client):
    assert "x-response-time-ms" in {k.lower() for k in client.get("/api/health").headers}
