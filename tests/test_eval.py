from __future__ import annotations

import pytest

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
from verbatim.eval.run_eval import load_questions


def test_relevance_matching_is_case_insensitive():
    assert relevance_vector(["Form EX-114 is required"], ["ex-114"]) == [1]


def test_relevance_vector_marks_misses():
    assert relevance_vector(["unrelated", "form EX-114"], ["EX-114"]) == [0, 1]


def test_hit_rate_is_binary_over_the_window():
    assert hit_rate([0, 0, 1], k=3) == 1.0
    assert hit_rate([0, 0, 1], k=2) == 0.0


def test_precision_is_divided_by_k_not_by_results_returned():
    # Two results, one relevant, k=5 -> 0.2, not 0.5.
    assert precision_at_k([1, 0], k=5) == pytest.approx(0.2)


def test_recall_caps_at_one():
    assert recall_at_k([1, 1, 1], k=3, total_relevant=2) == 1.0


def test_recall_without_a_relevant_passage_is_zero():
    assert recall_at_k([0, 0], k=2, total_relevant=0) == 0.0


def test_reciprocal_rank_uses_the_first_hit():
    assert reciprocal_rank([0, 1, 1]) == pytest.approx(0.5)
    assert reciprocal_rank([0, 0]) == 0.0


def test_ndcg_rewards_ranking_the_hit_higher():
    assert ndcg_at_k([1, 0, 0], k=3) > ndcg_at_k([0, 0, 1], k=3)


def test_ndcg_is_one_when_every_hit_is_at_the_top():
    assert ndcg_at_k([1, 1, 0], k=3) == pytest.approx(1.0)


def test_report_summary_averages_and_lists_failures():
    report = EvaluationReport(label="test", k=5)
    report.scores = [
        QuestionScore("a", 1.0, 0.2, 1.0, 1.0, 1.0, 3),
        QuestionScore("b", 0.0, 0.0, 0.0, 0.0, 0.0, 5),
    ]
    summary = report.summary()
    assert summary["hit@5"] == 0.5
    assert summary["questions"] == 2
    assert [score.question for score in report.failures()] == ["b"]


def test_question_file_parsing_skips_blanks_and_comments(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text(
        '# a comment\n\n{"question": "Q?", "expected": ["A"]}\n',
        encoding="utf-8",
    )
    assert load_questions(path) == [{"question": "Q?", "expected": ["A"]}]


def test_question_file_missing_a_field_is_rejected(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text('{"question": "Q?"}\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        load_questions(path)


def test_malformed_json_names_the_line(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="not valid JSON"):
        load_questions(path)
