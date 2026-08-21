"""Retrieval evaluation harness.

Usage:
    python -m verbatim.eval.run_eval eval/questions.jsonl
    python -m verbatim.eval.run_eval eval/questions.jsonl --compare

Each line of the input file is a JSON object:

    {"question": "...", "expected": ["substring that a correct passage contains"]}

--compare re-runs the same questions under dense-only, lexical-only and hybrid
settings. That table is the reason the hybrid default is the default; without
it, the alpha value is just a number somebody picked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from verbatim.eval.metrics import (
    EvaluationReport,
    QuestionScore,
    hit_rate,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    relevance_vector,
)
from verbatim.service import RagService

console = Console()
app = typer.Typer(add_completion=False)

# alpha, use_mmr, label - the three configurations worth comparing.
_COMPARISONS = [
    (1.0, False, "dense only"),
    (0.0, False, "lexical only"),
    (0.6, False, "hybrid"),
    (0.6, True, "hybrid + mmr"),
]


def load_questions(path: Path) -> list[dict]:
    questions = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{number} is not valid JSON: {exc}") from exc
        if "question" not in record or "expected" not in record:
            raise SystemExit(f"{path}:{number} needs both 'question' and 'expected'")
        questions.append(record)
    if not questions:
        raise SystemExit(f"{path} contains no questions")
    return questions


def evaluate(service: RagService, questions: list[dict], k: int, label: str) -> EvaluationReport:
    report = EvaluationReport(label=label, k=k)
    for record in questions:
        result = service.search(record["question"], top_k=k)
        texts = [chunk.text for chunk in result.chunks]
        relevance = relevance_vector(texts, record["expected"])
        report.scores.append(
            QuestionScore(
                question=record["question"],
                hit=hit_rate(relevance, k),
                precision=precision_at_k(relevance, k),
                recall=recall_at_k(relevance, k, len(record["expected"])),
                reciprocal_rank=reciprocal_rank(relevance),
                ndcg=ndcg_at_k(relevance, k),
                took_ms=result.took_ms,
                top_text=texts[0][:80] if texts else "",
            )
        )
    return report


def print_summary(reports: list[EvaluationReport]) -> None:
    columns = list(reports[0].summary().keys())
    table = Table(*columns, title="Retrieval evaluation")
    for report in reports:
        summary = report.summary()
        table.add_row(*(str(summary[column]) for column in columns))
    console.print(table)


def print_failures(report: EvaluationReport) -> None:
    failures = report.failures()
    if not failures:
        console.print("[green]Every question retrieved at least one relevant passage.")
        return
    table = Table("Question", "Top passage", title=f"{len(failures)} misses")
    for score in failures:
        table.add_row(score.question, score.top_text or "[dim]nothing retrieved")
    console.print(table)


@app.command()
def main(
    questions_file: Path = typer.Argument(..., exists=True),
    k: int = typer.Option(5, "--k", help="Cut-off for the @k metrics."),
    compare: bool = typer.Option(False, "--compare", help="Sweep retrieval configurations."),
    json_out: Path | None = typer.Option(None, "--json", help="Write the summary as JSON."),
) -> None:
    questions = load_questions(questions_file)
    service = RagService()
    if service.store.count() == 0:
        console.print("[red]The index is empty. Run `verbatim ingest ./samples` first.")
        raise typer.Exit(1)

    console.print(
        f"[dim]{len(questions)} questions - {service.store.count()} chunks - "
        f"{service.embedder.model} - k={k}"
    )

    base = service.settings
    reports: list[EvaluationReport] = []
    configurations = _COMPARISONS if compare else [(base.hybrid_alpha, base.use_mmr, "configured")]

    for alpha, use_mmr, label in configurations:
        service.retriever.hybrid_alpha = alpha
        service.retriever.use_mmr = use_mmr
        reports.append(evaluate(service, questions, k, label))

    service.retriever.hybrid_alpha = base.hybrid_alpha
    service.retriever.use_mmr = base.use_mmr

    print_summary(reports)
    print_failures(reports[-1])

    if json_out:
        payload = {
            "k": k,
            "chunks": service.store.count(),
            "embedding": service.embedder.describe(),
            "results": [report.summary() for report in reports],
        }
        json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"[dim]wrote {json_out}")

    # Non-zero exit when the configured setup misses more than a third of the
    # questions, so this can be wired into CI as a regression gate.
    if reports[-1].summary()[f"hit@{k}"] < 0.66:
        sys.exit(2)


if __name__ == "__main__":
    app()
