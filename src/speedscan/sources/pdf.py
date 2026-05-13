# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
# ^ pymupdf ships only partial type stubs; relax the strict "unknown" reports
# for this file rather than thread `cast()` through every line. Our own
# variables (page_number, total, etc.) stay annotated and the public surface
# is still strict.

"""PDF source: extracts text from PDFs using pymupdf.

Each page's text is split on whitespace into tokens; attached punctuation
stays glued to the word it touches (so "hello," is one item). Page
numbers are 1-based and reported via PageLocation.

Extraction quality depends heavily on the source PDF — multi-column
layouts, footnotes, and headers can interleave with body text. pymupdf
is the leading general-purpose Python option; per design §10 the
`TextSource` protocol keeps us free to A/B alternates later without
touching the engine or renderer.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pymupdf

from speedscan.sources.base import PageLocation, ProgressCallback, TextItem


class PdfSource:
    """TextSource for PDF files. Conforms to the TextSource Protocol."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def extract(self, progress: ProgressCallback | None = None) -> Iterator[TextItem]:
        with pymupdf.open(self.path) as doc:
            total: int = doc.page_count
            for page_index in range(total):
                page = doc.load_page(page_index)
                page_number = page_index + 1
                # get_text() is typed as a union (str | list | dict) over its
                # mode parameter; the no-arg default returns str.
                text = cast(str, page.get_text())
                for token in text.split():
                    yield TextItem(
                        text=token,
                        location=PageLocation(page=page_number),
                        level=0,
                    )
                if progress is not None:
                    progress(page_number, total)
