"""The document catalogue.

The vector store knows about chunks; the UI needs to talk about files - name,
type, size, when it was added, how many chunks it produced. Keeping that in its
own SQLite table means listing documents is one query instead of a full scan of
the index.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from verbatim.models import DocumentRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    source_type TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    char_count  INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS documents_created_at ON documents (created_at DESC);
"""


class DocumentCatalogue:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        self._db.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"],
            title=row["title"],
            source_type=row["source_type"],
            chunk_count=row["chunk_count"],
            char_count=row["char_count"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata"]),
        )

    def upsert(self, record: DocumentRecord) -> None:
        with self._lock:
            self._db.execute(
                """
                INSERT INTO documents (id, title, source_type, chunk_count, char_count,
                                       created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    chunk_count=excluded.chunk_count,
                    char_count=excluded.char_count,
                    metadata=excluded.metadata
                """,
                (
                    record.id,
                    record.title,
                    record.source_type,
                    record.chunk_count,
                    record.char_count,
                    record.created_at,
                    json.dumps(record.metadata),
                ),
            )
            self._db.commit()

    def get(self, document_id: str) -> DocumentRecord | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list(self, limit: int = 200, offset: int = 0) -> list[DocumentRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM documents ORDER BY created_at DESC, title LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def delete(self, document_id: str) -> bool:
        with self._lock:
            cursor = self._db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            self._db.commit()
            return cursor.rowcount > 0

    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM documents")
            self._db.commit()

    def totals(self) -> dict[str, int]:
        with self._lock:
            row = self._db.execute(
                "SELECT COUNT(*) AS documents, "
                "COALESCE(SUM(chunk_count), 0) AS chunks, "
                "COALESCE(SUM(char_count), 0) AS characters FROM documents"
            ).fetchone()
        return {k: int(row[k]) for k in ("documents", "chunks", "characters")}
