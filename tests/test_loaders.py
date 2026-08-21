from __future__ import annotations

import json

import pytest

from verbatim.ingest.loaders import UnsupportedFileType, load_document, normalise


def write(tmp_path, name: str, body: str):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_normalise_rejoins_hyphenated_line_breaks():
    assert "hyphenated" in normalise("hyphen-\nated word")


def test_normalise_drops_bare_page_numbers():
    assert normalise("Real content\n12\nMore content") == "Real content\nMore content"


def test_normalise_collapses_runs_of_blank_lines():
    assert normalise("a\n\n\n\n\nb") == "a\n\nb"


def test_markdown_headings_become_segment_context(tmp_path):
    path = write(tmp_path, "notes.md", "# Alpha\n\nFirst body.\n\n## Beta\n\nSecond body.\n")
    document = load_document(path)
    headings = [segment.heading for segment in document.segments]
    assert headings == ["Alpha", "Beta"]


def test_markdown_fenced_code_is_not_read_as_headings(tmp_path):
    path = write(tmp_path, "code.md", "# Title\n\n```\n# not a heading\n```\n")
    document = load_document(path)
    assert all(segment.heading == "Title" for segment in document.segments)


def test_html_strips_scripts_and_navigation(tmp_path):
    path = write(
        tmp_path,
        "page.html",
        "<html><body><nav>menu</nav><script>evil()</script>"
        "<h1>Heading</h1><p>Kept text.</p></body></html>",
    )
    text = load_document(path).text
    assert "Kept text." in text
    assert "evil" not in text and "menu" not in text


def test_csv_rows_are_rendered_as_labelled_fields(tmp_path):
    path = write(tmp_path, "rows.csv", "name,role\nAda,Engineer\nGrace,Admiral\n")
    text = load_document(path).text
    assert "name: Ada" in text and "role: Admiral" in text


def test_json_records_are_indexed_individually(tmp_path):
    path = write(tmp_path, "data.json", json.dumps([{"a": 1}, {"a": 2}]))
    assert len(load_document(path).segments) == 2


def test_title_defaults_to_a_readable_filename(tmp_path):
    path = write(tmp_path, "employee_handbook_2026.txt", "Body.")
    assert load_document(path).title == "employee handbook 2026"


def test_unsupported_extension_is_rejected(tmp_path):
    path = write(tmp_path, "binary.exe", "nope")
    with pytest.raises(UnsupportedFileType):
        load_document(path)


def test_empty_file_raises_a_useful_error(tmp_path):
    path = write(tmp_path, "blank.txt", "   \n\n  ")
    with pytest.raises(ValueError, match="No extractable text"):
        load_document(path)
