# pyright: reportUnknownMemberType=false
# ^ pymupdf ships partial stubs for the writer-side API (new_page,
# insert_text, save) used only by the test helper.

"""Behavior tests for PdfSource.

PDFs are generated on the fly with pymupdf so we don't carry binary
fixtures in the repo. Generation uses a different code path
(`insert_text`) than extraction (`get_text`), so round-tripping still
exercises the real library.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pymupdf
import pytest

from speedscan.sources.base import PageLocation, TextItem
from speedscan.sources.pdf import PdfSource


def _write_pdf(path: Path, pages: Iterable[str]) -> None:
    """Write a minimal PDF with one text block per page."""
    with pymupdf.open() as doc:
        for body in pages:
            page = doc.new_page()
            if body:
                page.insert_text((72, 72), body)
        doc.save(path)


def test_yields_one_item_per_word(tmp_path: Path) -> None:
    pdf = tmp_path / "single.pdf"
    _write_pdf(pdf, ["hello world"])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["hello", "world"]


def test_assigns_page_one_to_single_page(tmp_path: Path) -> None:
    pdf = tmp_path / "single.pdf"
    _write_pdf(pdf, ["alpha beta gamma"])

    items = list(PdfSource(pdf).extract())

    assert all(item.location == PageLocation(page=1) for item in items)


def test_increments_page_number_across_pages(tmp_path: Path) -> None:
    pdf = tmp_path / "multi.pdf"
    _write_pdf(pdf, ["first page", "second page", "third"])

    items = list(PdfSource(pdf).extract())

    pages = [item.location for item in items]
    assert pages == [
        PageLocation(page=1),
        PageLocation(page=1),
        PageLocation(page=2),
        PageLocation(page=2),
        PageLocation(page=3),
    ]


def test_preserves_attached_punctuation(tmp_path: Path) -> None:
    pdf = tmp_path / "punct.pdf"
    _write_pdf(pdf, ["hello, world! it's fine."])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["hello,", "world!", "it's", "fine."]


def test_blank_page_yields_no_items_for_that_page(tmp_path: Path) -> None:
    pdf = tmp_path / "blank_middle.pdf"
    _write_pdf(pdf, ["first", "", "third"])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["first", "third"]
    assert [item.location for item in items] == [PageLocation(page=1), PageLocation(page=3)]


def test_level_is_zero_for_every_item(tmp_path: Path) -> None:
    pdf = tmp_path / "level.pdf"
    _write_pdf(pdf, ["one two three"])

    items = list(PdfSource(pdf).extract())

    assert all(item.level == 0 for item in items)


def test_progress_callback_invoked_once_per_page(tmp_path: Path) -> None:
    pdf = tmp_path / "progress.pdf"
    _write_pdf(pdf, ["one", "two", "three"])
    calls: list[tuple[int, int]] = []

    list(PdfSource(pdf).extract(progress=lambda done, total: calls.append((done, total))))

    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_progress_callback_optional(tmp_path: Path) -> None:
    pdf = tmp_path / "no_progress.pdf"
    _write_pdf(pdf, ["just words"])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["just", "words"]


def test_path_attribute_exposed(tmp_path: Path) -> None:
    pdf = tmp_path / "x.pdf"
    _write_pdf(pdf, ["x"])

    source = PdfSource(pdf)

    assert source.path == pdf


def test_yields_text_item_instances(tmp_path: Path) -> None:
    pdf = tmp_path / "types.pdf"
    _write_pdf(pdf, ["word"])

    items = list(PdfSource(pdf).extract())

    assert all(isinstance(item, TextItem) for item in items)


def test_raises_on_corrupt_pdf(tmp_path: Path) -> None:
    # Magic bytes look right but the rest is garbage. pymupdf raises
    # FileDataError; we let it propagate so the CLI can present an
    # actionable message rather than silently producing nothing.
    pdf = tmp_path / "corrupt.pdf"
    pdf.write_bytes(b"%PDF-1.7\nnot actually a pdf body")

    with pytest.raises(pymupdf.FileDataError):
        list(PdfSource(pdf).extract())
