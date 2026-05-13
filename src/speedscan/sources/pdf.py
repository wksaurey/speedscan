# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
# ^ pymupdf ships only partial type stubs; relax the strict "unknown" reports
# for this file rather than thread `cast()` through every line. Our own
# variables (page_number, total, etc.) stay annotated and the public surface
# is still strict.

"""PDF source: extracts text from PDFs using pymupdf.

Words are split on whitespace; attached punctuation stays glued to the
word it touches (so "hello," is one item). Page numbers are 1-based and
reported via PageLocation.

# Line-break dehyphenation

Print-formatted PDFs hyphenate words at the right margin ("graphi-" /
"cally"). pymupdf's text extractor preserves the hyphen verbatim, which
shows up in RSVP as two unreadable half-words. We rejoin them using
position from `get_text("dict")`: when a *line's* last token ends in
`-`, the next line's first token is a candidate for joining.

The guard against merging lexical compounds ("all-stop", "self-aware")
is twofold:
  1. Lexical hyphens almost always live mid-line. We only inspect
     end-of-line trailing hyphens, so "all-stop button" is one token and
     never enters the dehyphenation path.
  2. Genuine compounds that happen to fall right at a line break are
     ambiguous from text alone. We require the continuation to start
     with a lowercase letter — proper nouns ("Co-\nOperative Boston")
     and digits ("page 14-\n15") stay split. Compounds whose second
     half begins lowercase ("self-\nawareness") will still be merged
     incorrectly; that's a known false-positive accepted as the price
     of a clean general fix.

Extraction quality depends heavily on the source PDF — multi-column
layouts, footnotes, and headers can interleave with body text. pymupdf
is the leading general-purpose Python option; per design §10 the
`TextSource` protocol keeps us free to A/B alternates later without
touching the engine or renderer.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pymupdf

from speedscan.sources.base import PageLocation, ProgressCallback, TextItem


class PdfSource:
    """TextSource for PDF files. Conforms to the TextSource Protocol."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def extract(self, progress: ProgressCallback | None = None) -> Iterator[TextItem]:
        with pymupdf.open(self.path) as doc:
            total: int = doc.page_count
            # A hyphenated word may bridge a line — or even a page — break.
            # Hold the trailing half until we see what follows.
            pending: tuple[str, int] | None = None

            for page_index in range(total):
                page = doc.load_page(page_index)
                page_number = page_index + 1

                for line_text in _page_lines(page):
                    words = line_text.split()
                    if not words:
                        continue

                    if pending is not None:
                        pending_word, pending_page = pending
                        head = words[0]
                        if head[:1].islower():
                            yield _item(pending_word[:-1] + head, pending_page)
                        else:
                            yield _item(pending_word, pending_page)
                            yield _item(head, page_number)
                        pending = None
                        words = words[1:]

                    for w in words[:-1]:
                        yield _item(w, page_number)

                    if words:
                        last = words[-1]
                        if len(last) > 1 and last.endswith("-"):
                            pending = (last, page_number)
                        else:
                            yield _item(last, page_number)

                if progress is not None:
                    progress(page_number, total)

            # Document ended with an unresolved trailing hyphen — emit it
            # as-is rather than dropping the word entirely.
            if pending is not None:
                yield _item(pending[0], pending[1])


def _item(text: str, page: int) -> TextItem:
    return TextItem(text=text, location=PageLocation(page=page), level=0)


def _page_lines(page: pymupdf.Page) -> Iterator[str]:
    """Yield each visual line of text on `page` as a single concatenated string.

    Uses pymupdf's dict-mode extraction so we can see line boundaries
    (raw `get_text()` flattens lines into one stream and loses the
    information dehyphenation needs).
    """
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:  # 0 = text block, 1 = image
            continue
        for line in block.get("lines", []):
            yield "".join(span.get("text", "") for span in line.get("spans", []))
