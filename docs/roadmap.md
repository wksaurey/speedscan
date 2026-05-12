# SpeedScan roadmap

Tracks deferred work after v1. See [`design.md`](design.md) §9 for context.

## v1.1 — Document structure, chunking, distribution

Cut from v1 to keep the initial release tight. The v1 data model already
carries the `level` field on `TextItem`, so these all land additively
without engine or renderer rewrites.

### Header detection and banner rendering

- **PDF**: detect H1/H2/H3 from font-size and weight deltas (`pymupdf`
  exposes per-span font metrics).
- **TXT**: opt-in heuristic detection via `--detect-txt-headers` flag —
  ALL CAPS lines, surrounding blank lines, leading `#`, numbered
  prefixes. Off by default; misfires easily without explicit markup.
- **Banner rendering** tier by level: H1 with ~2s pause, H2 with ~1s
  pause, H3+ inline as accent-colored body words. Pause durations user-
  configurable, scale inversely with WPM, may be set to 0 to disable
  while keeping the visual flag.
- Engine precomputes `header_index: list[(word_idx, level, text)]` at
  load time for O(log n) jumps and scope queries.

### Word chunking

- Bundle adjacent short body words below a configurable character
  threshold (default 12 chars **combined**) into single display ticks.
- ORP highlight anchors on the **first word's ORP character** for
  visual stability.
- One display tick per chunk at the user's WPM.
- Chunks never cross sentence/clause boundaries.
- Default off; toggle via setting.

### Scope-aware progress bar

- Cycle file → chapter → section → file via click on the bar or `\` key.
- Label shows current scope (`29% · book`, `60% · ch. 7`, `88% · §7.3`).
- Smart cycling skips scopes that don't apply to the current file.
- Preference persisted globally in `~/.config/speedscan/settings.json`.
- Chapter option in the Go-To dialog enabled.

### PyPI publish

- PyPI publish on tag push (Trusted Publishing — no API tokens).
- README install instructions update: `pip install speedscan`.
- (CI workflow ships in v1.0; v1.1 just adds the tag-triggered release job.)

## v1.2 — Standalone binaries

- GitHub Actions matrix build (Windows / macOS / Linux runners)
- PyInstaller bundles each platform into a single executable
- Uploaded to GitHub Release alongside source artifacts on tag push

**Heads-up:** customtkinter ships theme/font assets in its package
directory that PyInstaller does not auto-bundle. The build job will need
explicit `--add-data` flags (or a `.spec` file) pointing at
customtkinter's `assets/`. Plan ~half a day for binary debugging on the
first cut.

## v2 candidates

Roughly prioritized:

- `.epub` source via `ebooklib`
- `.html` source via `BeautifulSoup`
- `.docx` source via `python-docx`
- "Go to" dialog with fuzzy section search
- Configurable end-of-sentence/paragraph pause — short dwell on
  terminal punctuation so the reader can consolidate the clause before
  the next one arrives. User-tunable (e.g. 0–500ms sentence, longer for
  paragraph); set to 0 to disable.
- Optional TUI renderer (textual)
- `.mobi`, `.fb2` for completeness
- Full content sniffing via `puremagic` or `python-magic` — v1's
  hand-rolled `%PDF-` check stops being sufficient once we discriminate
  among 5+ formats with potentially overlapping byte signatures

## Risks tracked from design

- **PDF text extraction quality** — A/B `pymupdf` vs `pdfplumber` vs `pypdf`
  against several real textbooks (multi-column papers, scientific PDFs with
  footnotes, etc.). Add an `--extract-preview` CLI mode to sanity-check
  ordering before reading.
- **ORP under HiDPI** — verify rendering on at least one HiDPI display.
- **Cross-platform Tk keybinding parity** — document tested OS/version pairs.
