"""Tests for the sources/__init__.py factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from speedscan.sources import SOURCES, source_for
from speedscan.sources.txt import TxtSource


class TestSourceFor:
    def test_routes_plain_text_to_txt_source(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_bytes(b"hello world\n")

        assert isinstance(source_for(f), TxtSource)

    def test_misnamed_text_file_still_routes_to_txt(self, tmp_path: Path) -> None:
        # File pretending to be a PDF by extension, but actual content
        # is plain text. Sniff must win over the suffix.
        f = tmp_path / "fake.pdf"
        f.write_bytes(b"this is just plain text\n")

        assert isinstance(source_for(f), TxtSource)

    def test_pdf_magic_raises_not_implemented(self, tmp_path: Path) -> None:
        # PDF starts with `%PDF-` per the spec. Until PdfSource lands,
        # the factory should fail loudly rather than silently treating
        # binary PDF bytes as Latin-1 text.
        f = tmp_path / "real.pdf"
        f.write_bytes(b"%PDF-1.7\n...binary garbage...")

        with pytest.raises(NotImplementedError, match="PDF"):
            source_for(f)

    def test_pdf_magic_misnamed_as_txt_still_raises(self, tmp_path: Path) -> None:
        # PDF bytes wearing a .txt suffix — sniff still catches it.
        f = tmp_path / "misnamed.txt"
        f.write_bytes(b"%PDF-1.4\n...")

        with pytest.raises(NotImplementedError):
            source_for(f)

    def test_empty_file_routes_to_txt(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")

        assert isinstance(source_for(f), TxtSource)


class TestSourcesRegistry:
    def test_txt_format_registered(self) -> None:
        assert SOURCES["txt"] is TxtSource
