# SpeedScan — UI mockups

Low-fidelity wireframes of every view. ASCII layouts capture intent only;
exact pixel measurements, fonts, and colors are decided in implementation.

The window is resizable; mockups show approximate proportions for a default
~720×480 size.

---

## 1. Idle / file picker

Shown on launch with no file argument, after `Esc` from any other view, and
after closing a file.

```
┌─────────────────────────────────────────────────────────────┐
│  SpeedScan                                            ─ □ × │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│                    Open a file to begin                     │
│                                                             │
│                       [ Open… ]   ⌃O                        │
│                                                             │
│                                                             │
│   Recent                                                    │
│   ─────────────────────────────                             │
│   Campbell Biology Concepts.pdf            p. 247 of 856    │
│   Sporre — Perceiving the Arts.pdf         p. 89 of 412     │
│   stat3000-course-reader.pdf               p. 12 of 198     │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ⌃O open · ⌃Q quit                                          │
└─────────────────────────────────────────────────────────────┘
```

**Notes**

- Recent file list pulls resume positions from `persistence.py`.
- Clicking a recent file opens it and resumes at the saved position.
- `⌃O` shows the system file picker.

---

## 2. Reading view (body word with ORP)

The main view. One word at a time, with the ORP (Optimal Recognition Point) character pinned at a fixed x.

```
┌─────────────────────────────────────────────────────────────┐
│  SpeedScan — Campbell Biology.pdf                     ─ □ × │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│                                                             │
│                       mit●hondria                           │
│                          ↑                                  │
│                       ORP-x (fixed)                         │
│                                                             │
│                       p. 247 of 856                         │
│                                                             │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ▶ 400 wpm   ━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░  29%         │
└─────────────────────────────────────────────────────────────┘
```

**Notes**

- `●` marks the ORP character (rendered in accent color in the real UI).
- ORP-x is constant; pre-ORP characters (`mit`) right-align to it,
  post-ORP characters (`hondria`) left-align from it.
- The visual word "shifts" so the ORP character stays put. This is the
  whole point of Spritz-style RSVP.
- Status bar: play/pause icon · WPM · progress bar · % through document.

---

## 3. Reading view — chunked words *(v1.1 preview — not in v1)*

When chunking is enabled and short adjacent words bundle into one tick:

```
                       of●the
                          ↑
                       ORP-x  (still pinned to the first word's ORP)
```

**Notes**

- ORP highlight stays on the first word's ORP character, not recomputed
  for the combined chunk — recomputing would shift the visual anchor and
  feel disorienting at speed.
- Whole chunk gets a single display tick at the user's WPM.

---

## 4. Header banner (H1 / H2) *(v1.1 preview — not in v1)*

Replaces the word view when the engine emits a header item. Tier by level.

```
┌─────────────────────────────────────────────────────────────┐
│  SpeedScan — Campbell Biology.pdf                     ─ □ × │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│        ┌─────────────────────────────────────────┐          │
│        │                                         │          │
│        │       Chapter 7: The Cell Cycle         │          │
│        │                                         │          │
│        └─────────────────────────────────────────┘          │
│                                                             │
│                       p. 246 of 856                         │
│                       ⏸  pausing 2.0s                       │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ⏸ 400 wpm   ━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░  28%         │
└─────────────────────────────────────────────────────────────┘
```

**Notes**

- H1 frame is heavier; H2 is lighter; H3+ skips the banner entirely and
  renders inline as accent-colored body words.
- Pause indicator counts down so the user knows how long until reading
  resumes.
- `Space` skips the pause; `←` returns to the previous body word.

---

## 5. Go-to dialog

Modal launched by `⌃G`.

```
┌─────────────────────────────────────────────────────────────┐
│  SpeedScan — Campbell Biology.pdf                     ─ □ × │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│        ┌───────────────────────────────────────┐            │
│        │  Go to                                │            │
│        │  ─────────────────                    │            │
│        │  ○ Page    [  247  ]   of 856         │            │
│        │  ○ Word    [        ]   of 234,201    │            │
│        │                                       │            │
│        │              [ Cancel ]   [ Go ]      │            │
│        └───────────────────────────────────────┘            │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ⏸ 400 wpm   ━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░  29%          │
└─────────────────────────────────────────────────────────────┘
```

**Notes**

- Two radio options in v1: page or word index.
- v1.1 will add a Chapter option (dropdown of detected headers) once
  header detection ships.
- `Esc` cancels; `Enter` confirms current selection.

---

## 6. First open — extracting (cache miss)

Shown the first time a file is opened. Subsequent opens load from cache and
go straight to the reading view (<1s).

```
┌─────────────────────────────────────────────────────────────┐
│  SpeedScan — Campbell Biology.pdf                     ─ □ × │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│                  Extracting text from PDF                   │
│                                                             │
│         ━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░░░░░  47%           │
│                                                             │
│                    page 234 of 502                          │
│                                                             │
│                       [ Cancel ]                            │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Extracting once · cached for next time                     │
└─────────────────────────────────────────────────────────────┘
```

**Notes**

- One-time cost per file. Result cached at `~/.cache/speedscan/<key>.json`.
- Cache key is content hash + extractor version, so a file modified on disk
  or a parser upgrade triggers re-extraction automatically.
- `Cancel` returns to the file picker; partial extracts are discarded.
- For txt files this screen is skipped — extraction is fast enough to
  complete before the picker dialog dismisses.

---

## What's intentionally not specified

- Exact font (system default sans is fine; pickable later)
- Exact accent / theme colors (customtkinter defaults are good; pick at
  implementation time)
- Animation between word/banner views (probably none — RSVP wants snap
  transitions, not crossfades)
- Resize behavior (font scales with window? fixed size with max-width?
  decide when it matters)
