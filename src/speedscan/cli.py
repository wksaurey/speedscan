"""Command-line entry point.

Wires the pipeline: source factory → cache → engine → renderer. Saves
resume position on quit. v1 requires a file argument; the no-file idle
screen with recents lands once the file picker is wired up.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from speedscan.cache import Cache, default_cache_dir, hash_file
from speedscan.engine import RsvpEngine
from speedscan.persistence import Persistence, default_config_dir
from speedscan.sources import source_for
from speedscan.sources.base import PageLocation, TextItem
from speedscan.ui.app import DocumentInfo, run


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="speedscan", description="RSVP text reader")
    p.add_argument("file", type=Path, help="path to a .txt (.pdf coming soon)")
    p.add_argument("--wpm", type=int, default=400, help="words per minute (default 400)")
    return p


def _max_page(items: list[TextItem]) -> int:
    max_page = 0
    for item in items:
        if isinstance(item.location, PageLocation):
            max_page = max(max_page, item.location.page)
    return max_page


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    path: Path = args.file

    if not path.exists():
        print(f"speedscan: file not found: {path}", file=sys.stderr)
        return 2
    if not path.is_file():
        print(f"speedscan: not a regular file: {path}", file=sys.stderr)
        return 2

    try:
        source = source_for(path)
    except NotImplementedError as e:
        print(f"speedscan: {e}", file=sys.stderr)
        return 3

    cache = Cache(default_cache_dir())
    persistence = Persistence(default_config_dir())

    items = cache.get_or_extract(source)
    if not items:
        print(f"speedscan: no text extracted from {path}", file=sys.stderr)
        return 4

    file_hash = hash_file(path)
    engine = RsvpEngine(items, wpm=args.wpm)
    resume_index = persistence.load_position(file_hash)
    if resume_index is not None and 0 <= resume_index < len(items):
        engine.seek_to_index(resume_index)

    doc = DocumentInfo(
        title=path.name,
        total_items=len(items),
        max_page=_max_page(items),
    )

    def _save_resume() -> None:
        persistence.save_position(file_hash, path, engine.current_index)

    run(engine, doc, on_quit=_save_resume)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
