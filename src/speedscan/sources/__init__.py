"""Pluggable text sources, one per file format.

This module dispatches a path to the right `TextSource` implementation.
Detection is by magic bytes, not extension, so a `.txt` file that's
actually a PDF still routes correctly (and a misnamed PDF doesn't crash
the txt decoder). See `base.py` for the protocol and `docs/design.md` §4
for architecture.

Adding a new format:
  1. Implement `TextSource` in `sources/<format>.py`.
  2. Add a sniff branch to `source_for()` if the format has a magic
     prefix; otherwise add an extension hint.
  3. Add the class to `SOURCES` for documentation / introspection.
"""

from __future__ import annotations

from pathlib import Path

from speedscan.sources.base import TextSource
from speedscan.sources.txt import TxtSource

# Public registry — keyed by short format name. Currently informational
# (the factory picks via magic bytes, not this dict). A future v2
# content sniff via puremagic/python-magic will consume it directly.
SOURCES: dict[str, type[TextSource]] = {"txt": TxtSource}

_SNIFF_BYTES = 5
_PDF_MAGIC = b"%PDF-"


def source_for(path: Path) -> TextSource:
    """Return the right TextSource for `path`, sniffing magic bytes."""
    head = _read_head(path)
    if head.startswith(_PDF_MAGIC):
        # PdfSource lands in a follow-up task; until then a PDF reaches
        # this branch only if the user explicitly opens one.
        raise NotImplementedError(
            "PDF support is not yet implemented. Open a .txt file or wait for the PdfSource task."
        )
    return TxtSource(path)


def _read_head(path: Path) -> bytes:
    with path.open("rb") as f:
        return f.read(_SNIFF_BYTES)
