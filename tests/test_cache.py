"""Tests for the disk cache.

Verifies hash key derivation, JSON round-trip for both LocationMarker
shapes, miss-then-hit behavior, corruption recovery, and progress
callback pass-through.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from speedscan.cache import Cache, default_cache_dir, hash_file
from speedscan.sources.base import (
    LineLocation,
    PageLocation,
    ProgressCallback,
    TextItem,
)


class _RecordingSource:
    """Source double that counts extract() calls."""

    def __init__(self, path: Path, items: list[TextItem]) -> None:
        self.path = path
        self._items = items
        self.extract_calls = 0

    def extract(self, progress: ProgressCallback | None = None) -> Iterator[TextItem]:
        self.extract_calls += 1
        total = len(self._items)
        for i, item in enumerate(self._items, start=1):
            if progress is not None:
                progress(i, total)
            yield item


def _write_file(path: Path, content: bytes) -> None:
    path.write_bytes(content)


class TestHashFile:
    def test_same_content_same_hash(self, tmp_path: Path) -> None:
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        _write_file(a, b"hello world")
        _write_file(b, b"hello world")
        assert hash_file(a) == hash_file(b)

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        _write_file(a, b"hello")
        _write_file(b, b"world")
        assert hash_file(a) != hash_file(b)

    def test_returns_16_char_hex(self, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        _write_file(f, b"any")
        key = hash_file(f)
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)


class TestDefaultCacheDir:
    def test_honors_xdg_cache_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        assert default_cache_dir() == tmp_path / "speedscan"

    def test_falls_back_to_home_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        assert default_cache_dir() == Path.home() / ".cache" / "speedscan"


class TestCacheGetOrExtract:
    def test_miss_calls_source_and_stores(self, tmp_path: Path) -> None:
        file_path = tmp_path / "doc.txt"
        _write_file(file_path, b"some content")
        cache = Cache(tmp_path / "cache")
        items = [TextItem(text="hello", location=LineLocation(line=1))]
        source = _RecordingSource(file_path, items)

        result = cache.get_or_extract(source)

        assert result == items
        assert source.extract_calls == 1

    def test_hit_returns_cached_without_re_extracting(self, tmp_path: Path) -> None:
        file_path = tmp_path / "doc.txt"
        _write_file(file_path, b"some content")
        cache = Cache(tmp_path / "cache")
        items = [TextItem(text="hi", location=PageLocation(page=1))]
        source = _RecordingSource(file_path, items)

        cache.get_or_extract(source)
        result = cache.get_or_extract(source)

        assert result == items
        assert source.extract_calls == 1  # second call hit the cache

    def test_round_trips_page_and_line_locations(self, tmp_path: Path) -> None:
        file_path = tmp_path / "doc.txt"
        _write_file(file_path, b"x")
        cache = Cache(tmp_path / "cache")
        items = [
            TextItem(text="word1", location=PageLocation(page=3)),
            TextItem(text="word2", location=LineLocation(line=42), level=1),
        ]
        source = _RecordingSource(file_path, items)

        cache.get_or_extract(source)
        # New cache instance — forces a disk read, not in-memory state.
        result = Cache(tmp_path / "cache").get_or_extract(source)

        assert result == items

    def test_progress_callback_passed_to_source_on_miss(self, tmp_path: Path) -> None:
        file_path = tmp_path / "doc.txt"
        _write_file(file_path, b"x")
        cache = Cache(tmp_path / "cache")
        items = [
            TextItem(text="a", location=LineLocation(line=1)),
            TextItem(text="b", location=LineLocation(line=2)),
        ]
        source = _RecordingSource(file_path, items)

        calls: list[tuple[int, int]] = []
        cache.get_or_extract(source, progress=lambda d, t: calls.append((d, t)))

        assert calls == [(1, 2), (2, 2)]

    def test_corrupted_cache_falls_back_to_extract(self, tmp_path: Path) -> None:
        file_path = tmp_path / "doc.txt"
        _write_file(file_path, b"content")
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        key = hash_file(file_path)
        (cache_dir / f"{key}.json").write_text("{not valid json")

        cache = Cache(cache_dir)
        items = [TextItem(text="ok", location=LineLocation(line=1))]
        source = _RecordingSource(file_path, items)

        result = cache.get_or_extract(source)

        assert result == items
        assert source.extract_calls == 1

    def test_stale_format_version_treated_as_miss(self, tmp_path: Path) -> None:
        file_path = tmp_path / "doc.txt"
        _write_file(file_path, b"content")
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        key = hash_file(file_path)
        (cache_dir / f"{key}.json").write_text(json.dumps({"version": 999, "items": []}))

        cache = Cache(cache_dir)
        items = [TextItem(text="x", location=LineLocation(line=1))]
        source = _RecordingSource(file_path, items)

        result = cache.get_or_extract(source)

        assert result == items
        assert source.extract_calls == 1

    def test_creates_cache_dir_if_missing(self, tmp_path: Path) -> None:
        file_path = tmp_path / "doc.txt"
        _write_file(file_path, b"content")
        nested = tmp_path / "deeply" / "nested" / "cache"
        cache = Cache(nested)
        source = _RecordingSource(file_path, [TextItem(text="x", location=LineLocation(line=1))])

        cache.get_or_extract(source)

        assert nested.is_dir()

    def test_does_not_leave_tmp_files_after_write(self, tmp_path: Path) -> None:
        file_path = tmp_path / "doc.txt"
        _write_file(file_path, b"content")
        cache_dir = tmp_path / "cache"
        cache = Cache(cache_dir)
        source = _RecordingSource(file_path, [TextItem(text="x", location=LineLocation(line=1))])

        cache.get_or_extract(source)

        tmp_leftovers = list(cache_dir.glob("*.tmp"))
        assert tmp_leftovers == []
