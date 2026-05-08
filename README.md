# SpeedScan

A lightweight desktop reader using Rapid Serial Visual Presentation (RSVP).
Loads `.txt` and `.pdf` files and displays them one word at a time at
configurable speed (up to ~1000 wpm), with Spritz-style ORP (Optimal
Recognition Point) rendering and full transport controls.

> **Status:** v0.1 — design complete, implementation in progress.
> See [`docs/design.md`](docs/design.md).

## Why

Reading speed is bottlenecked by saccadic eye movement, not by visual
recognition. RSVP eliminates that bottleneck by displaying one word at a time
at a fixed point on screen so the brain can process at its actual recognition
rate. SpeedScan is a personal tool for fast study and review of textbooks,
papers, and articles — surfacing the source location (page number, line) so
the original document can be opened separately for deep reading.

## Install

```bash
pip install git+https://github.com/wksaurey/speedscan.git
```

After v1.1 publishes to PyPI:

```bash
pip install speedscan
```

## Usage

```bash
speedscan path/to/file.pdf
```

Or open the app without arguments and pick a file from the in-app file picker.

### Keyboard

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `← →` | Prev / next word |
| `Shift+← →` | Prev / next sentence |
| `↑ ↓` | Decrease / increase WPM |
| `PgUp PgDn` | Prev / next page |
| `Ctrl+G` | Go to page or word index |
| `Ctrl+O` | Open file |
| `Esc` | Pause + open file |
| `Ctrl+Q` | Quit (saves resume position) |

## Supported formats

**v1:** `.txt`, `.pdf`

**Planned:** `.epub`, `.docx`, `.html`, `.mobi`, `.fb2` —
see [`docs/roadmap.md`](docs/roadmap.md).

## Development

```bash
git clone https://github.com/wksaurey/speedscan.git
cd speedscan
uv sync --all-extras           # or: pip install -e ".[dev]"
uv run pytest                  # tests
uv run ruff check .            # lint
uv run pyright                 # type check
uv run speedscan FILE          # run the app
```

See [`CLAUDE.md`](CLAUDE.md) for project conventions.

## License

MIT — see [`LICENSE`](LICENSE).

## Acknowledgements

Built collaboratively with [Claude Code](https://claude.com/claude-code).
The design phase that drove the implementation lives in
[`docs/design.md`](docs/design.md).
