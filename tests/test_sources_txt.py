"""Behavior tests for TxtSource."""

from __future__ import annotations

from pathlib import Path

from speedscan.sources.base import LineLocation, TextItem
from speedscan.sources.txt import TxtSource


def test_yields_one_item_per_word(tmp_path: Path) -> None:
    file = tmp_path / "hello.txt"
    file.write_text("hello world", encoding="utf-8")

    items = list(TxtSource(file).extract())

    assert [item.text for item in items] == ["hello", "world"]


def test_assigns_line_one_to_single_line_input(tmp_path: Path) -> None:
    file = tmp_path / "one_line.txt"
    file.write_text("alpha beta gamma", encoding="utf-8")

    items = list(TxtSource(file).extract())

    assert all(item.location == LineLocation(line=1) for item in items)


def test_increments_line_number_across_lines(tmp_path: Path) -> None:
    file = tmp_path / "multi.txt"
    file.write_text("first line\nsecond line\nthird\n", encoding="utf-8")

    items = list(TxtSource(file).extract())

    lines = [item.location for item in items]
    assert lines == [
        LineLocation(line=1),
        LineLocation(line=1),
        LineLocation(line=2),
        LineLocation(line=2),
        LineLocation(line=3),
    ]


def test_preserves_attached_punctuation(tmp_path: Path) -> None:
    file = tmp_path / "punct.txt"
    file.write_text("hello, world! it's fine.", encoding="utf-8")

    items = list(TxtSource(file).extract())

    assert [item.text for item in items] == ["hello,", "world!", "it's", "fine."]


def test_collapses_runs_of_whitespace(tmp_path: Path) -> None:
    file = tmp_path / "spaces.txt"
    file.write_text("a    b\t\tc", encoding="utf-8")

    items = list(TxtSource(file).extract())

    assert [item.text for item in items] == ["a", "b", "c"]


def test_empty_file_yields_no_items(tmp_path: Path) -> None:
    file = tmp_path / "empty.txt"
    file.write_text("", encoding="utf-8")

    items = list(TxtSource(file).extract())

    assert items == []


def test_level_is_zero_for_every_item(tmp_path: Path) -> None:
    file = tmp_path / "level.txt"
    file.write_text("one two three", encoding="utf-8")

    items = list(TxtSource(file).extract())

    assert all(item.level == 0 for item in items)


def test_decodes_utf16_le_with_bom(tmp_path: Path) -> None:
    file = tmp_path / "utf16le.txt"
    # \xff\xfe is the UTF-16-LE BOM.
    file.write_bytes(b"\xff\xfe" + "café résumé".encode("utf-16-le"))

    items = list(TxtSource(file).extract())

    assert [item.text for item in items] == ["café", "résumé"]


def test_decodes_utf16_be_with_bom(tmp_path: Path) -> None:
    file = tmp_path / "utf16be.txt"
    file.write_bytes(b"\xfe\xff" + "hola mundo".encode("utf-16-be"))

    items = list(TxtSource(file).extract())

    assert [item.text for item in items] == ["hola", "mundo"]


def test_falls_back_to_latin1_when_utf8_fails(tmp_path: Path) -> None:
    file = tmp_path / "latin1.txt"
    # \xe9 alone is invalid UTF-8 but valid latin-1 (é).
    file.write_bytes(b"caf\xe9 ole")

    items = list(TxtSource(file).extract())

    assert [item.text for item in items] == ["café", "ole"]


def test_progress_callback_invoked_when_provided(tmp_path: Path) -> None:
    file = tmp_path / "progress.txt"
    file.write_text("line one\nline two\nline three\n", encoding="utf-8")
    calls: list[tuple[int, int]] = []

    list(TxtSource(file).extract(progress=lambda done, total: calls.append((done, total))))

    assert len(calls) > 0


def test_progress_callback_reports_total_bytes(tmp_path: Path) -> None:
    file = tmp_path / "progress_total.txt"
    payload = "a b c\nd e f\n"
    file.write_text(payload, encoding="utf-8")
    calls: list[tuple[int, int]] = []

    list(TxtSource(file).extract(progress=lambda done, total: calls.append((done, total))))

    expected_total = len(payload.encode("utf-8"))
    assert all(total == expected_total for _, total in calls)


def test_progress_callback_optional(tmp_path: Path) -> None:
    file = tmp_path / "no_progress.txt"
    file.write_text("just words here", encoding="utf-8")

    # Act / Assert: should not raise when progress is None (the default).
    items = list(TxtSource(file).extract())

    assert len(items) == 3


def test_path_attribute_exposed(tmp_path: Path) -> None:
    file = tmp_path / "x.txt"
    file.write_text("", encoding="utf-8")

    source = TxtSource(file)

    assert source.path == file


def test_yields_text_item_instances(tmp_path: Path) -> None:
    file = tmp_path / "types.txt"
    file.write_text("word", encoding="utf-8")

    items = list(TxtSource(file).extract())

    assert all(isinstance(item, TextItem) for item in items)
