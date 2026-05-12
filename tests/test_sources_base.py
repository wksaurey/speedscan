"""Contract tests for sources/base.py.

Verifies the data types behave as expected and that a minimal in-memory
source structurally satisfies the TextSource Protocol.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from speedscan.sources.base import (
    LineLocation,
    LocationMarker,
    PageLocation,
    ProgressCallback,
    TextItem,
    TextSource,
)


class TestPageLocation:
    def test_constructs(self) -> None:
        loc = PageLocation(page=42)
        assert loc.page == 42

    def test_frozen(self) -> None:
        loc = PageLocation(page=1)
        with pytest.raises(FrozenInstanceError):
            loc.page = 2  # type: ignore[misc]

    def test_hashable(self) -> None:
        assert hash(PageLocation(page=1)) == hash(PageLocation(page=1))


class TestLineLocation:
    def test_constructs(self) -> None:
        loc = LineLocation(line=1842)
        assert loc.line == 1842

    def test_distinct_from_page_location(self) -> None:
        assert PageLocation(page=1) != LineLocation(line=1)


class TestTextItem:
    def test_constructs_with_defaults(self) -> None:
        item = TextItem(text="hello", location=PageLocation(page=1))
        assert item.text == "hello"
        assert item.location == PageLocation(page=1)
        assert item.level == 0

    def test_accepts_line_location(self) -> None:
        item = TextItem(text="hi", location=LineLocation(line=10))
        assert isinstance(item.location, LineLocation)

    def test_level_settable(self) -> None:
        item = TextItem(text="Chapter 1", location=PageLocation(page=1), level=1)
        assert item.level == 1

    def test_frozen(self) -> None:
        item = TextItem(text="x", location=PageLocation(page=1))
        with pytest.raises(FrozenInstanceError):
            item.text = "y"  # type: ignore[misc]


class _FakeSource:
    """Minimal in-memory source for structural conformance to TextSource."""

    def __init__(self, path: Path, items: list[TextItem]) -> None:
        self.path = path
        self._items = items

    def extract(self, progress: ProgressCallback | None = None) -> Iterator[TextItem]:
        total = len(self._items)
        for i, item in enumerate(self._items, start=1):
            if progress is not None:
                progress(i, total)
            yield item


class TestTextSourceProtocol:
    def test_fake_source_satisfies_protocol(self) -> None:
        items = [
            TextItem(text="one", location=LineLocation(line=1)),
            TextItem(text="two", location=LineLocation(line=1)),
        ]
        source: TextSource = _FakeSource(Path("/tmp/x.txt"), items)
        assert list(source.extract()) == items

    def test_progress_callback_invoked(self) -> None:
        items = [
            TextItem(text="a", location=PageLocation(page=1)),
            TextItem(text="b", location=PageLocation(page=1)),
            TextItem(text="c", location=PageLocation(page=2)),
        ]
        calls: list[tuple[int, int]] = []
        source = _FakeSource(Path("/tmp/x.pdf"), items)
        list(source.extract(progress=lambda done, total: calls.append((done, total))))
        assert calls == [(1, 3), (2, 3), (3, 3)]

    def test_progress_callback_optional(self) -> None:
        source = _FakeSource(Path("/tmp/x.txt"), [])
        assert list(source.extract()) == []


def test_location_marker_union_accepts_both() -> None:
    markers: list[LocationMarker] = [PageLocation(page=1), LineLocation(line=1)]
    assert len(markers) == 2
