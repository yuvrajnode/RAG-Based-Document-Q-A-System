"""Command line interface.

The API is the product, but ingesting a folder and sanity-checking retrieval
from a terminal is what you actually do while tuning, so both are first-class.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from verbatim import __version__
from verbatim.service import RagService

app = typer.Typer(help="Verbatim - retrieval-augmented Q&A over your documents.", no_args_is_help=True)
console = Console()


def _service() -> RagService:
    with console.status("[dim]loading index...", spinner="dots"):
        return RagService()


@app.command()
def ingest(
    path: Path = typer.Argument(..., exists=True, help="A file or a directory of files."),
) -> None:
    """Index a file or every supported file in a directory."""
    service = _service()
    results = service.ingest_directory(path) if path.is_dir() else [service.ingest_file(path)]
    if not results:
        console.print("[yellow]Nothing was ingested - no supported files found.")
        raise typer.Exit(1)

    table = Table("Document", "Type", "Chunks", "Chars", "ms", title=f"Ingested {len(results)}")
    for result in results:
        record = result.record
        table.add_row(
            record.title,
            record.source_type,
            str(record.chunk_count),
            f"{record.char_count:,}",
            str(result.took_ms),
        )
    console.print(table)


@app.command()
def ask(
    question: str = typer.Argument(...),
    top_k: int = typer.Option(5, "--top-k", "-k"),
    show_sources: bool = typer.Option(True, "--sources/--no-sources"),
) -> None:
    """Ask a question against the index."""
    service = _service()
    with console.status("[dim]thinking...", spinner="dots"):
        answer = service.ask(question, top_k=top_k)

    console.print()
    console.print(Markdown(answer.text))
    console.print()

    if show_sources and answer.citations:
        table = Table("#", "Document", "Page", "Snippet", title="Sources")
        for citation in answer.citations:
            table.add_row(
                str(citation.marker),
                citation.document_title,
                str(citation.page or "-"),
                citation.snippet[:90] + ("..." if len(citation.snippet) > 90 else ""),
            )
        console.print(table)
    console.print(f"[dim]{answer.model} - {answer.latency_ms}ms")


@app.command()
def search(query: str = typer.Argument(...), top_k: int = typer.Option(8, "--top-k", "-k")) -> None:
    """Show what retrieval returns, without generating an answer."""
    result = _service().search(query, top_k=top_k)
    table = Table("Score", "Dense", "BM25", "Document", "Passage", title=result.strategy)
    for chunk in result.chunks:
        table.add_row(
            f"{chunk.score:.3f}",
            f"{chunk.dense_score:.3f}",
            f"{chunk.lexical_score:.2f}",
            chunk.document_title,
            " ".join(chunk.text.split())[:70] + "...",
        )
    console.print(table)
    console.print(f"[dim]{result.took_ms}ms - {result.dense_candidates} dense / "
                  f"{result.lexical_candidates} lexical candidates")


@app.command("list")
def list_documents() -> None:
    """List indexed documents."""
    service = _service()
    records = service.documents()
    if not records:
        console.print("[yellow]The index is empty. Run `verbatim ingest <path>` first.")
        return
    table = Table("Id", "Document", "Type", "Chunks", "Added")
    for record in records:
        table.add_row(
            record.id[:8], record.title, record.source_type, str(record.chunk_count), record.created_at
        )
    console.print(table)


@app.command()
def delete(document_id: str = typer.Argument(...)) -> None:
    """Remove a document and its chunks from the index."""
    if _service().delete_document(document_id):
        console.print(f"[green]Deleted {document_id}")
    else:
        console.print(f"[red]No document with id {document_id}")
        raise typer.Exit(1)


@app.command()
def stats() -> None:
    """Show the running configuration and index size."""
    data = _service().stats()
    table = Table("Setting", "Value")
    table.add_row("version", __version__)
    table.add_row("documents", str(data["documents"]))
    table.add_row("chunks", str(data["chunks"]))
    table.add_row("vector store", data["vector_store"])
    table.add_row("embeddings", f"{data['embedding']['model']} (dim {data['embedding']['dimension']})")
    table.add_row("llm", data["llm"]["model"] or "not configured")
    table.add_row("retrieval", data["retrieval"]["strategy"])
    console.print(table)


if __name__ == "__main__":
    app()
