"""Plain-text source: parses .txt files into a TextItem stream.

Words are split on whitespace; attached punctuation stays glued to the
word it touches (so "hello," is one item). Line numbers are 1-based and
reported via LineLocation.

Encoding is detected in this order:
  1. UTF-8 strict — covers the vast majority of modern text files.
  2. UTF-16 — only when a BOM (\\xff\\xfe or \\xfe\\xff) is present at byte 0.
     Without a BOM we can't reliably distinguish UTF-16 from random binary,
     so we don't guess.
  3. Latin-1 — guaranteed fallback. Latin-1 maps every byte to a codepoint,
     so it never raises. Wrong codepoints beat a crash for a personal
     reading tool.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from speedscan.sources.base import LineLocation, ProgressCallback, TextItem


class TxtSource:
    """TextSource for plain-text files. Conforms to the TextSource Protocol."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def extract(self, progress: ProgressCallback | None = None) -> Iterator[TextItem]:
        raw = self.path.read_bytes()
        total = len(raw)
        text = _decode(raw)

        # splitlines() handles \n, \r\n, and \r consistently and drops the
        # trailing newline. keepends=False is the default.
        lines = text.splitlines()

        # Per-line progress: report bytes consumed proportional to line count.
        # We don't track exact byte offsets per line (re-encoding to count
        # would defeat the point), so we approximate with line-index * total
        # / len(lines). For a personal RSVP tool this is sufficient — the
        # progress bar is only there to reassure the user something is
        # happening on large files.
        line_count = len(lines)
        for line_index, line in enumerate(lines, start=1):
            for token in line.split():
                yield TextItem(text=token, location=LineLocation(line=line_index), level=0)
            if progress is not None and line_count > 0:
                done = (line_index * total) // line_count
                progress(done, total)

        # Empty file: still fire progress(0, 0) so callers see a terminal call.
        if progress is not None and line_count == 0:
            progress(total, total)


def _decode(raw: bytes) -> str:
    """Decode bytes using UTF-8 → UTF-16-with-BOM → Latin-1.

    Latin-1 is the guaranteed fallback: every byte sequence decodes
    without raising. The result may misrepresent non-ASCII characters,
    but the file will at least open and scroll.
    """
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    return raw.decode("latin-1")
