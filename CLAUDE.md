# SpeedScan — project conventions

This file orients future Claude (or any contributor) working in the repo.
Read [`docs/design.md`](docs/design.md) first for any non-trivial change.

## What this is

A desktop RSVP reader for `.txt` and `.pdf` (more formats planned). Personal
tool, MIT-licensed, intended to be installable via `pip` and eventually
shipped as standalone binaries.

## Tech stack

- **Python 3.11+** — modern typing (`Self`, PEP 695 generics, etc.)
- **customtkinter** — GUI. Tk-shaped API with modern theming.
- **pymupdf** — PDF text extraction (current leading candidate; may A/B vs `pdfplumber` per design §10)
- **uv** — dev environment manager. Plain `pip` works as fallback.
- **ruff** — lint + format
- **pyright** — strict type checking
- **pytest** — tests

## Layout

`src/` layout. Tests can't import the working tree without `pip install -e .`.

```
src/speedscan/
├── __main__.py      # `python -m speedscan`
├── cli.py           # arg parsing → wire engine + renderer
├── engine.py        # RsvpEngine — pure logic, no GUI imports
├── cache.py         # disk cache for parsed TextItem[] (~/.cache/speedscan/)
├── persistence.py   # resume positions (~/.config/speedscan/)
├── sources/         # TextSource implementations (one per file format)
└── ui/              # customtkinter renderer
```

## Key abstractions

- **`TextSource` (Protocol)** in `sources/base.py` — every format implementer
  yields `TextItem(text, location, level)`. Engine consumes the stream
  blind to format. In v1 `level` is always `0`; v1.1 will populate it for
  detected headers (the field is reserved now so v1.1 lands additively).
- **`Cache`** in `cache.py` — sits between sources and the engine. Hashes
  the file content, returns cached `TextItem[]` if present, otherwise
  triggers `source.extract()` and writes the result. Sources don't know
  the cache exists.
- **`RsvpEngine`** in `engine.py` — pure logic, no GUI imports. Owns the
  `TextItem` stream, current index, WPM, and play/pause state. Emits
  events the renderer subscribes to.
- **`Renderer`** in `ui/app.py` — customtkinter app, subscribes to engine
  events.

## Adding a new file format

1. Create `src/speedscan/sources/<format>.py` implementing `TextSource`.
2. Register the extension in `src/speedscan/sources/__init__.py` `SOURCES` dict.
3. Add fixtures + tests under `tests/`.
4. Update `docs/roadmap.md`.

The engine and renderer should not need changes.

## Don't do

- Don't import any GUI lib (`customtkinter`, `tkinter`) from `engine.py` or
  `sources/`. Engine is pure logic; sources are pure parsers. If a feature
  seems to need cross-layer imports, the layering is wrong.
- Don't add an embedded PDF viewer. v1 surfaces page numbers; users open the
  source file separately. (`docs/design.md` §2 non-goals.)
- Don't add features beyond the v1 scope without updating `docs/design.md`
  first.

## Run commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run pyright
uv run speedscan FILE
```

## Git workflow

Solo repo, but feature-branch flow regardless: branch off `main`, commit via
the `/commit` skill (never raw `git commit`), fast-forward merge back, push.
Conventional commit prefixes (`feat:`, `fix:`, `docs:`, `test:`, `chore:`,
`refactor:`).
