"""Source contract: TextItem, LocationMarker, TextSource Protocol.

Every file-format implementation in `sources/` produces a stream of
TextItem instances. The engine consumes the stream blind to format.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias


@dataclass(frozen=True, slots=True)
class PageLocation:
    page: int


@dataclass(frozen=True, slots=True)
class LineLocation:
    line: int


LocationMarker: TypeAlias = PageLocation | LineLocation


@dataclass(frozen=True, slots=True)
class TextItem:
    text: str
    location: LocationMarker
    level: int = 0


ProgressCallback: TypeAlias = Callable[[int, int], None]


class TextSource(Protocol):
    """Yields TextItem instances from a single file.

    Implementations live in `sources/<format>.py` and register in
    `sources/__init__.py`. Sources are pure parsers — no knowledge of
    the cache, engine, or UI.
    """

    path: Path

    def extract(self, progress: ProgressCallback | None = None) -> Iterator[TextItem]:
        """Parse `self.path` and yield TextItems in reading order.

        `progress(done, total)` is called periodically with units of the
        source's choosing (pages for PDFs, bytes for txt). `total` may
        be 0 when the source can't determine it upfront.
        """
        ...
