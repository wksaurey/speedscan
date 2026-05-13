"""RsvpEngine — pure logic for RSVP playback.

The engine owns the TextItem stream, current index, WPM, and transport
state (EngineState). It does NOT own a timer; the renderer drives word
advancement using Tk's `after()`, scheduled at `current_word_delay_ms`.

This module must not import any GUI library (tkinter, customtkinter) so
that engine logic stays unit-testable and decoupled from the renderer.
See design.md §4.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from speedscan.sources.base import LocationMarker, TextItem

# WPM bounds per design.md §4. 100 is the floor for "still reading not
# falling asleep"; 1500 is the ceiling beyond which the renderer can't
# keep up and the reader can't perceive words.
_WPM_MIN = 100
_WPM_MAX = 1500

# Hold the current word slightly longer when it ends in punctuation so
# the reader gets a beat at clause and sentence boundaries. Multipliers
# applied over the base 60_000//wpm delay. Standard RSVP convention.
_SENTENCE_END = (".", "!", "?", "…")  # period, bang, question, ellipsis
_CLAUSE_END = (",", ";", ":", "—")  # comma, semicolon, colon, em-dash
_SENTENCE_MULTIPLIER = 2.0
_CLAUSE_MULTIPLIER = 1.5
# Strip closing punctuation/quotes before checking the trailing char so
# `end."` and `(hello!)` still get the sentence-end pause.
_TRAILING_TRIM = "\"')]}»”’"  # noqa: RUF001  curly quotes intentional — match real PDF text


class EngineState(StrEnum):
    IDLE = "idle"
    EXTRACTING = "extracting"
    PLAYING = "playing"
    PAUSED = "paused"


DisplayCallback = Callable[[TextItem], None]
StateChangeCallback = Callable[[EngineState], None]


class RsvpEngine:
    """Pure-logic RSVP engine.

    The renderer subscribes to `on_display` (fired when the current item
    changes) and `on_state_change` (fired only on actual transitions).
    Advancement timing is the renderer's responsibility — it reads
    `current_word_delay_ms` and schedules the next tick via `after()`.
    """

    def __init__(self, items: list[TextItem], wpm: int = 400) -> None:
        self._items: list[TextItem] = items
        self._index: int = 0
        self._wpm: int = _clamp_wpm(wpm)
        # Empty stream → IDLE (nothing to display). Otherwise start paused
        # so the renderer can decide when to begin playback.
        self._state: EngineState = EngineState.PAUSED if items else EngineState.IDLE
        self._display_subs: list[DisplayCallback] = []
        self._state_subs: list[StateChangeCallback] = []

    # ── transport ───────────────────────────────────────────────────────

    def play(self) -> None:
        # No-op when there's nothing to play. IDLE is the empty-stream
        # state and must not silently flip to PLAYING.
        if self._state is EngineState.IDLE:
            return
        self._set_state(EngineState.PLAYING)

    def pause(self) -> None:
        self._set_state(EngineState.PAUSED)

    def step(self, n: int) -> None:
        """Advance index by signed `n`, clamped to valid range.

        Clamping (rather than raising) lets the renderer call `step(+1)`
        on a timer without special-casing the boundary.
        """
        if not self._items:
            return
        new_index = _clamp(self._index + n, 0, len(self._items) - 1)
        if new_index != self._index:
            self._index = new_index
            self._fire_display()

    def seek_to_index(self, i: int) -> None:
        if not (0 <= i < len(self._items)):
            raise ValueError(
                f"seek index {i} out of range [0, {len(self._items)}); "
                "pass an index within the loaded item stream."
            )
        if i != self._index:
            self._index = i
            self._fire_display()

    def seek_to_location(self, marker: LocationMarker) -> None:
        """Seek to the first item matching `marker` (dataclass equality)."""
        for i, item in enumerate(self._items):
            if item.location == marker:
                self.seek_to_index(i)
                return
        raise ValueError(
            f"no item with location {marker!r} in stream; "
            "the marker may be from a different file or out of range."
        )

    def set_wpm(self, wpm: int) -> None:
        self._wpm = _clamp_wpm(wpm)

    # ── read-only state ─────────────────────────────────────────────────

    @property
    def current_item(self) -> TextItem | None:
        if not self._items:
            return None
        return self._items[self._index]

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def wpm(self) -> int:
        return self._wpm

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def current_word_delay_ms(self) -> int:
        # 60_000 ms/min ÷ wpm = base ms per word. The current item gets
        # a longer pause when it ends in punctuation; see _SENTENCE_END /
        # _CLAUSE_END.
        base = 60_000 // self._wpm
        item = self.current_item
        if item is None:
            return base
        return int(base * _punctuation_multiplier(item.text))

    # ── subscriptions ───────────────────────────────────────────────────

    def subscribe_on_display(self, cb: DisplayCallback) -> None:
        self._display_subs.append(cb)

    def subscribe_on_state_change(self, cb: StateChangeCallback) -> None:
        self._state_subs.append(cb)

    # ── internals ───────────────────────────────────────────────────────

    def _set_state(self, new_state: EngineState) -> None:
        if new_state is self._state:
            return
        self._state = new_state
        for cb in self._state_subs:
            cb(new_state)

    def _fire_display(self) -> None:
        item = self.current_item
        if item is None:
            return
        for cb in self._display_subs:
            cb(item)


def _clamp(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _clamp_wpm(wpm: int) -> int:
    return _clamp(wpm, _WPM_MIN, _WPM_MAX)


def _punctuation_multiplier(text: str) -> float:
    """Return the delay multiplier for a token based on its trailing punctuation."""
    inner = text.rstrip(_TRAILING_TRIM)
    if inner.endswith(_SENTENCE_END):
        return _SENTENCE_MULTIPLIER
    if inner.endswith(_CLAUSE_END):
        return _CLAUSE_MULTIPLIER
    return 1.0
