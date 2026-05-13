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


def _write_pdf_lines(path: Path, pages: Iterable[Iterable[str]]) -> None:
    """Write a PDF where each page is a list of explicitly-positioned lines.

    Used to force pymupdf's dict extractor to see specific line breaks —
    necessary for dehyphenation tests.
    """
    with pymupdf.open() as doc:
        for lines in pages:
            page = doc.new_page()
            for index, line in enumerate(lines):
                page.insert_text((72, 72 + 20 * index), line)
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


def test_joins_hyphenated_word_across_lines(tmp_path: Path) -> None:
    pdf = tmp_path / "hyphen.pdf"
    _write_pdf_lines(pdf, [["graphi-", "cally detailed"]])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["graphically", "detailed"]


def test_preserves_lexical_hyphen_within_token(tmp_path: Path) -> None:
    # "all-stop" is a single token in the source — no whitespace inside,
    # so it never enters the dehyphenation path and stays intact.
    pdf = tmp_path / "lex.pdf"
    _write_pdf(pdf, ["the all-stop button"])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["the", "all-stop", "button"]


def test_does_not_join_when_continuation_starts_uppercase(tmp_path: Path) -> None:
    # Uppercase next line signals a proper noun or sentence start, not a
    # continuation of a hyphenated stem.
    pdf = tmp_path / "upper.pdf"
    _write_pdf_lines(pdf, [["co-", "Operative Boston"]])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["co-", "Operative", "Boston"]


def test_does_not_join_when_continuation_starts_with_digit(tmp_path: Path) -> None:
    # Numeric range "14-\n15", not a hyphenated word.
    pdf = tmp_path / "digit.pdf"
    _write_pdf_lines(pdf, [["page 14-", "15 of the report"]])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["page", "14-", "15", "of", "the", "report"]


def test_joins_hyphenated_word_across_pages(tmp_path: Path) -> None:
    # Hyphenation can bridge a page break in printed books.
    pdf = tmp_path / "cross_page.pdf"
    _write_pdf_lines(pdf, [["begin-"], ["ning starts here"]])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["beginning", "starts", "here"]


def test_joined_word_location_is_page_where_hyphen_appeared(tmp_path: Path) -> None:
    # Reader sees the joined word first on the page where the hyphen
    # lived — anchor location there so the page counter lines up.
    pdf = tmp_path / "loc.pdf"
    _write_pdf_lines(pdf, [["begin-"], ["ning here"]])

    items = list(PdfSource(pdf).extract())

    assert items[0].text == "beginning"
    assert items[0].location == PageLocation(page=1)
    assert items[1].location == PageLocation(page=2)


def test_trailing_hyphen_at_end_of_document_emitted_as_is(tmp_path: Path) -> None:
    # Nothing follows — emit the partial token rather than dropping it.
    pdf = tmp_path / "trailing.pdf"
    _write_pdf_lines(pdf, [["sentence ends with stem-"]])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["sentence", "ends", "with", "stem-"]


def test_solo_hyphen_at_line_end_not_treated_as_hyphenation(tmp_path: Path) -> None:
    # A bare "-" (length 1) is a dash/bullet, not a word stem awaiting
    # a continuation.
    pdf = tmp_path / "solo.pdf"
    _write_pdf_lines(pdf, [["item -", "next thing"]])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["item", "-", "next", "thing"]


def test_collapses_letterspaced_uppercase_title(tmp_path: Path) -> None:
    # Typographic letter-spacing ("C H A P T E R") shows up as separate
    # tokens to pymupdf; we re-stitch them.
    pdf = tmp_path / "title.pdf"
    _write_pdf(pdf, ["C H A P T E R  2"])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["CHAPTER", "2"]


def test_collapses_letterspaced_with_three_letter_minimum(tmp_path: Path) -> None:
    # Two-letter runs are ordinary words ("A B" could be initials);
    # only collapse 3+.
    pdf = tmp_path / "short.pdf"
    _write_pdf(pdf, ["A B is fine but X Y Z collapses"])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["A", "B", "is", "fine", "but", "XYZ", "collapses"]


def test_does_not_collapse_lowercase_singles(tmp_path: Path) -> None:
    # "a b c" mid-sentence stays apart — lowercase letter-spacing is
    # rare enough we don't infer it from singletons.
    pdf = tmp_path / "lower.pdf"
    _write_pdf(pdf, ["a b c are first letters"])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["a", "b", "c", "are", "first", "letters"]


def test_does_not_collapse_across_a_lowercase_break(tmp_path: Path) -> None:
    # The run must be continuous uppercase singletons.
    pdf = tmp_path / "broken.pdf"
    _write_pdf(pdf, ["A B and X Y Z"])

    items = list(PdfSource(pdf).extract())

    assert [item.text for item in items] == ["A", "B", "and", "XYZ"]


def test_raises_on_corrupt_pdf(tmp_path: Path) -> None:
    # Magic bytes look right but the rest is garbage. pymupdf raises
    # FileDataError; we let it propagate so the CLI can present an
    # actionable message rather than silently producing nothing.
    pdf = tmp_path / "corrupt.pdf"
    pdf.write_bytes(b"%PDF-1.7\nnot actually a pdf body")

    with pytest.raises(pymupdf.FileDataError):
        list(PdfSource(pdf).extract())
