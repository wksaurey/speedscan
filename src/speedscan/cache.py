"""Disk cache for parsed TextItem streams.

Sits between TextSource implementations and the engine. On open, hashes
the file content and looks for a cached TextItem[]; on cache miss, runs
the source's extract() and writes the result. Sources are oblivious.

Cache format is JSON-only. Switching to pickle would turn cache files
into a code-execution vector for anyone with write access to the cache
directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from speedscan.sources.base import (
    LineLocation,
    LocationMarker,
    PageLocation,
    ProgressCallback,
    TextItem,
    TextSource,
)

_HASH_PREFIX_LEN = 16
_READ_CHUNK = 64 * 1024
_CACHE_FORMAT_VERSION = 1


def default_cache_dir() -> Path:
    """Resolve XDG cache directory for SpeedScan.

    Honors `$XDG_CACHE_HOME` when set, otherwise `~/.cache/speedscan`.
    """
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "speedscan"


def hash_file(path: Path) -> str:
    """Stream sha256 over file bytes and return the first 16 hex chars."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_READ_CHUNK):
            h.update(chunk)
    return h.hexdigest()[:_HASH_PREFIX_LEN]


def _location_to_dict(loc: LocationMarker) -> dict[str, Any]:
    if isinstance(loc, PageLocation):
        return {"kind": "page", "page": loc.page}
    return {"kind": "line", "line": loc.line}


def _location_from_dict(d: dict[str, Any]) -> LocationMarker:
    kind = d["kind"]
    if kind == "page":
        return PageLocation(page=int(d["page"]))
    if kind == "line":
        return LineLocation(line=int(d["line"]))
    raise ValueError(f"unknown location kind: {kind!r}")


def _item_to_dict(item: TextItem) -> dict[str, Any]:
    return {
        "text": item.text,
        "location": _location_to_dict(item.location),
        "level": item.level,
    }


def _item_from_dict(d: dict[str, Any]) -> TextItem:
    return TextItem(
        text=str(d["text"]),
        location=_location_from_dict(d["location"]),
        level=int(d.get("level", 0)),
    )


class Cache:
    """Hash-keyed disk cache for TextItem[] payloads.

    Caller-provided directory keeps the class fully testable. The CLI is
    expected to wire `default_cache_dir()` in at startup.
    """

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    def get_or_extract(
        self,
        source: TextSource,
        progress: ProgressCallback | None = None,
    ) -> list[TextItem]:
        """Return cached items if present, otherwise extract and store."""
        key = hash_file(source.path)
        cache_path = self.cache_dir / f"{key}.json"

        cached = self._try_load(cache_path)
        if cached is not None:
            return cached

        items = list(source.extract(progress))
        self._store(cache_path, items)
        return items

    def _try_load(self, cache_path: Path) -> list[TextItem] | None:
        if not cache_path.exists():
            return None
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if payload.get("version") != _CACHE_FORMAT_VERSION:
                return None
            return [_item_from_dict(d) for d in payload["items"]]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Corrupted or stale-schema cache — treat as a miss so the
            # source re-extracts and overwrites cleanly.
            return None

    def _store(self, cache_path: Path, items: list[TextItem]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _CACHE_FORMAT_VERSION,
            "items": [_item_to_dict(item) for item in items],
        }
        # Atomic write: tmp file + rename, so a crash mid-write never
        # leaves a partial JSON file in the cache.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.cache_dir,
            prefix=cache_path.stem + ".",
            suffix=".tmp",
            delete=False,
        ) as f:
            json.dump(payload, f)
            tmp_name = f.name
        os.replace(tmp_name, cache_path)
