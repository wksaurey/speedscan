# SpeedScan — design

## 1. Problem statement

Reading large volumes of text is bottlenecked by saccadic eye movement, not
visual recognition. RSVP (Rapid Serial Visual Presentation) shows one word at
a time at a fixed point so the brain can process at its actual recognition
rate (600+ wpm vs. ~250 wpm free reading). SpeedScan is a personal tool for
fast study and review: load a textbook or article, scan it at 4–6× normal
speed, and surface the source location (page number, line) so the user can
jump back into the original document.

## 2. Goals / Non-goals

**Goals (v1)**

- Read `.txt` and `.pdf` at up to ~1000 wpm with low-latency transport
- Spritz-style ORP (Optimal Recognition Point) rendering: one character pinned at a fixed x, highlighted
- Transport: play/pause, prev/next word, prev/next sentence, speed ±,
  jump-to-page, file picker
- Surface current location (page, line) — user opens source separately
- Single-command install (`pip install speedscan`)
- Cross-platform (Linux primary; Windows/macOS expected to work)
- Type-checked, tested, MIT-licensed

**Non-goals (v1)**

- Embedded PDF viewer or in-app source navigation
- DRM/protected formats
- Comprehension scoring, quizzes, vocab tracking
- Web/mobile/server — desktop only

## 3. Requirements

### Functional

- **F1** — Open file from CLI arg or in-app file picker
- **F2** — Sequential word display at configurable WPM (default 400, range 100–1500)
- **F3** — ORP character at fixed x-coordinate, highlighted in accent color
- **F4** — Keyboard transport (full table in §6)
- **F5** — Status display: word, location label (`p. 47 of 312`), WPM, % progress through file
- **F6** — Per-file resume position across sessions
- **F7** — Idle screen shows the N most-recently-opened files with their saved positions; clicking one opens the file and resumes at the saved position. List persisted alongside resume state.

Header detection, banner rendering, word chunking, and scope-aware progress
are deferred to v1.1; the `level` field on `TextItem` is reserved for them
in v1's data model so they land additively. See [`roadmap.md`](roadmap.md).

### Non-functional

- **N1** — **Cache-warm open**: file → first word displayed in <1s for files of any reasonable size
- **N1b** — **First-time extract (cache miss)**: may take 10–30s for a 500-page PDF; the renderer shows the extract-progress screen during the `EXTRACTING` state
- **N2** — Input-to-screen latency < 16ms
- **N3** — Clean shutdown, no leaked file handles
- **N4** — Type-checked (pyright strict), engine + sources unit-tested (pytest)
- **N5** — MIT license

## 4. Architecture

Three layers decoupled by protocol boundaries:

```
┌──────────────────────────┐
│ Renderer (customtkinter) │   word + ORP + status + keybindings
└────────────▲─────────────┘
             │ Word events ↑↓ control events
┌────────────┴─────────────┐
│      RsvpEngine          │   index, scheduler, transport state
└────────────▲─────────────┘
             │ TextItem[]
┌────────────┴─────────────┐
│       Cache              │   ~/.cache hit, else extract via TextSource
└────────────▲─────────────┘
             │ yields TextItem(text, location, level)
┌────────────┴─────────────┐
│ TextSource (Protocol)    │   txt / pdf  →  epub / docx / html …
└──────────────────────────┘
```

### Types

```python
@dataclass(frozen=True, slots=True)
class PageLocation:
    page: int

@dataclass(frozen=True, slots=True)
class LineLocation:
    line: int

LocationMarker = PageLocation | LineLocation
# v2 extends the union: ChapterLocation, ParagraphLocation, AnchorLocation, …

@dataclass(frozen=True, slots=True)
class TextItem:
    text: str
    location: LocationMarker
    level: int = 0   # 0 = body word; ≥1 = header level (v1 always emits 0)

class EngineState(StrEnum):
    IDLE       = "idle"        # no file loaded
    EXTRACTING = "extracting"  # cache miss, source is parsing
    PLAYING    = "playing"     # actively advancing
    PAUSED     = "paused"      # stopped on current word
```

The renderer pattern-matches on `LocationMarker` to produce the status
label (`p. 47 of 312`, `line 1842`). Adding a new format that introduces
a new location shape = add a dataclass + extend the union; engine and
renderer don't change shape, only their `match` arms grow.

### Components

**`TextSource` (Protocol)** — concrete implementations: `TxtSource`,
`PdfSource`. Yields `TextItem(text, location, level)` where `level=0` is a
body word and `level≥1` indicates a header (H1, H2, …).

**Format dispatch** is a small factory in `sources/__init__.py` that
sniffs magic bytes (`%PDF-` → `PdfSource`; everything else → `TxtSource`).
The file extension is a hint for the file picker, not the sole signal,
so misnamed files still route correctly. The text path tries
UTF-8 → UTF-16 (with BOM) → Latin-1 in order, handling Project Gutenberg
and DOS-encoded `.txt` files without configuration. Adding a new format =
implement `TextSource` + extend the factory's sniff + register the class;
engine and renderer don't change.

A full libmagic-style content sniff is overkill for v1 (only two
formats) and deferred to v2 when more formats land — see roadmap.

**`Cache`** — sits between `TextSource` and the engine. On open: hash the
file content (`sha256(file_bytes)[:16]`) and look up
`~/.cache/speedscan/<key>.json`. Cache hit → return parsed `TextItem[]`
instantly (<1s). Cache miss → run the source's `extract()` (which reports
its own progress), write result to cache, return. Source classes don't
know the cache exists. No eviction in v1; textbook-sized parses are
10–30 MB of JSON each, so unbounded growth is not a real concern at
expected use volumes. Extractor-version invalidation and LRU are
deferred to v1.1+ — additive when either becomes a concrete problem.

Cache format is **JSON only**. Switching to `pickle` would turn cache
files into a code-execution vector for anyone with write access to
`~/.cache/speedscan/`; the dataclass-serialization convenience is not
worth that.

**`RsvpEngine`** — pure logic, no GUI imports. Owns the `TextItem` stream,
current index, WPM, and an `EngineState`. Methods: `play()`, `pause()`,
`step(±n)`, `seek_to_index(i)`, `seek_to_location(marker)`. Emits
`on_display(item: TextItem)` and `on_state_change(state: EngineState)`.
The renderer pattern-matches on `EngineState` to switch UI mode (idle
screen, extract-progress screen, reading view ▶/⏸) and gate keybindings.
In v1 every `TextItem` has `level=0`; v1.1 adds level-dependent header
behavior and word chunking on top of the same engine and event surface.

**`Renderer`** — customtkinter app. Listens to engine events, sends control
input. ORP word rendering uses a 3-column layout: pre-ORP label right-anchored
to ORP-x, ORP character at fixed ORP-x in accent color, post-ORP label
left-anchored from ORP-x. Everything else is stock widgets.

**Persistence** — `~/.config/speedscan/state.json`, keyed by file hash so
renames don't lose resume position.

## 5. Project structure

```
speedscan/
├── README.md                   # install, usage, screenshot, license
├── LICENSE                     # MIT
├── CLAUDE.md                   # project conventions for Claude
├── pyproject.toml              # build, deps, [project.scripts] entry
├── .gitignore
├── .github/workflows/
│   ├── ci.yml                  # ruff + pyright + pytest
│   └── release.yml             # PyInstaller binaries on tag      (v1.2)
├── .claude/
│   └── settings.json           # project-scoped permissions
├── docs/
│   ├── design.md               # this document
│   ├── roadmap.md              # deferred formats + features
│   └── screenshots/
├── src/speedscan/
│   ├── __init__.py
│   ├── __main__.py             # `python -m speedscan`
│   ├── cli.py                  # arg parsing → wire engine + renderer
│   ├── engine.py               # RsvpEngine
│   ├── cache.py                # disk cache for parsed TextItem[]
│   ├── persistence.py          # resume positions (XDG config)
│   ├── sources/
│   │   ├── __init__.py         # SOURCES registry + factory
│   │   ├── base.py             # TextSource Protocol, TextItem, LocationMarker
│   │   ├── txt.py
│   │   └── pdf.py
│   └── ui/
│       ├── __init__.py
│       ├── app.py              # customtkinter app + event wiring
│       ├── word_view.py        # ORP-rendering widget
│       └── controls.py         # keybindings, status bar
└── tests/
    ├── test_engine.py
    ├── test_sources_txt.py
    ├── test_sources_pdf.py
    └── fixtures/
```

`src/` layout means tests can't accidentally pick up the working tree without
an install (`pip install -e .`).

## 6. UI / UX

ASCII wireframes of each view live in [`ui-mockup.md`](ui-mockup.md).

### Display

- Centered word (default 48pt), ORP character in accent color, baseline pinned to ORP-x
- Below word: location label (`p. 47 of 312` for PDF, `line 1842` for txt)
- Bottom status bar: filename · WPM · play/pause icon · % progress
- Dark theme default; toggleable

### Keybindings

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `→` / `←` | Next / previous word |
| `Shift+→` / `Shift+←` | Next / previous sentence |
| `↑` / `↓` | WPM ± 25 |
| `PgDn` / `PgUp` | Next / previous page (or section) |
| `Ctrl+G` | Go-to dialog (word index or page #) |
| `Ctrl+O` | Open file picker |
| `Esc` | Close any open modal; otherwise pause + return to file picker |
| `Ctrl+Q` | Quit (saves resume position) |

## 7. Tooling

- **Python 3.11+** — modern typing, no reason to support older
- **uv** — dev env manager (fast, modern, single-binary); pip works as fallback
- **ruff** — lint + format (replaces black/isort/flake8)
- **pyright** — type checking, strict mode
- **pytest** — tests
- **pre-commit** — runs ruff + pyright on staged files

## 8. Distribution

Three phases, additive — none replaces a previous one.

**Phase 1 (v0.1 → v1.0): source install.** `pyproject.toml` with
`[project.scripts] speedscan = "speedscan.cli:main"`. Users install via
`pip install git+https://github.com/wksaurey/speedscan` or clone +
`pip install -e .`. README documents both. Goal: working end-to-end before
publishing anywhere.

**Phase 2 (v1.1): PyPI.** `python -m build` → wheel + sdist. GitHub Actions on
tag push → upload via PyPI Trusted Publishing (no API tokens).
`pip install speedscan` works for everyone.

**Phase 3 (v1.2): standalone binaries.** GitHub Actions matrix
(Win/macOS/Linux) → PyInstaller → upload to GitHub Release alongside source on
tag. README adds "download for your OS" section. PyPI install remains primary.

The two install paths coexist cleanly because they share no build artifacts —
PyInstaller bundles its own Python interpreter, completely independent of pip
wheels.

## 9. Roadmap

- **v1.0** (target: one weekend): txt, pdf, ORP rendering, full transport,
  resume position, simple disk cache, CI workflow (ruff + pyright +
  pytest), MIT, README, pyproject, basic tests. `pip install -e .` works
  end-to-end.
- **v1.1**: header detection + banner rendering, word chunking,
  scope-aware progress bar, PyPI publish on tag. See
  [`roadmap.md`](roadmap.md).
- **v1.2**: PyInstaller release workflow.
- **v2 candidates** (prioritized): `.epub` (ebooklib) → `.html` (BeautifulSoup)
  → `.docx` (python-docx) → fuzzy "go to" → auto-pause on punctuation →
  optional TUI renderer (textual) → `.mobi`/`.fb2`.

## 10. Risks & open questions

- **PDF text extraction quality** — multi-column layouts, footnotes, and
  headers can interleave with body text. `pymupdf` is the leading
  general-purpose Python option, but extraction quality varies wildly by
  source PDF. Mitigation: (a) build an `--extract-preview` mode that dumps the
  first N words so the user can sanity-check ordering before reading;
  (b) keep `PdfSource` behind the `TextSource` protocol so we can A/B
  alternate extractors (`pdfplumber`, `pypdf`, OCR via `tesseract`) without
  touching the engine or renderer.
- **ORP under DPI scaling** — fixed x-coordinate must scale with font size and
  screen DPI. Test on at least one HiDPI display.
- **Tk keybinding portability** — `Shift+Arrow` and `Ctrl+G` semantics vary by
  platform. Document tested OS/version pairs.

## 11. Claude usage (portfolio note)

[`CLAUDE.md`](../CLAUDE.md) documents project conventions for any future
Claude session: Python version, src layout, customtkinter, ORP-based RSVP, run
commands, and the recipe for adding a new format. `.claude/settings.json`
holds only project-scoped permissions — no personal hooks or memory. README
openly credits Claude as a development tool; commits carry an attribution
trailer.
