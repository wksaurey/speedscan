"""ORP word rendering.

The Optimal Recognition Point is a single character in each word that
the eye fixates on most readily. Spritz-style RSVP pins that character
at a fixed x-coordinate on screen so the visual anchor never moves —
your eye stops saccading and the brain processes words at recognition
rate (~600 wpm) instead of saccade rate (~250 wpm).

This widget draws one word with:
  - pre-ORP characters right-anchored to (orp_x - orp_char_width/2)
  - ORP character centered at orp_x, in accent color
  - post-ORP characters left-anchored from (orp_x + orp_char_width/2)

A monospace font is used deliberately: variable-width fonts make the
ORP-x math depend on each character's metrics, which adds complexity
without a meaningful UX win for streaming-word display.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from speedscan.sources.base import TextItem

_DEFAULT_FONT_FAMILY = "Courier"
_DEFAULT_FONT_SIZE = 48
_DEFAULT_ACCENT = "#FF5555"
_DEFAULT_FG = "#E0E0E0"
_DEFAULT_BG = "#1E1E1E"


def orp_index(word: str) -> int:
    """Return the ORP character index for `word` using the Spritz table.

    Empty strings return 0. Spritz's published heuristic biases the ORP
    slightly left of center so longer words still feel readable.
    """
    n = len(word)
    if n <= 1:
        return 0
    if n <= 5:
        return 1
    if n <= 9:
        return 2
    if n <= 13:
        return 3
    return 4


def split_at_orp(word: str) -> tuple[str, str, str]:
    """Split `word` into (pre, orp_char, post) around its ORP index."""
    if not word:
        return "", "", ""
    i = orp_index(word)
    return word[:i], word[i], word[i + 1 :]


class WordView(tk.Canvas):
    """Canvas widget that draws a single TextItem with ORP highlight."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        font_family: str = _DEFAULT_FONT_FAMILY,
        font_size: int = _DEFAULT_FONT_SIZE,
        accent: str = _DEFAULT_ACCENT,
        fg: str = _DEFAULT_FG,
        bg: str = _DEFAULT_BG,
    ) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0)
        self._font = tkfont.Font(family=font_family, size=font_size)
        self._accent = accent
        self._fg = fg
        self._current: TextItem | None = None
        self.bind("<Configure>", self._on_resize)

    def display(self, item: TextItem) -> None:
        """Render `item.text` with the ORP character highlighted."""
        self._current = item
        self._redraw()

    def clear(self) -> None:
        self._current = None
        self.delete("all")

    def _on_resize(self, _event: tk.Event[tk.Misc]) -> None:
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        item = self._current
        if item is None:
            return

        pre, orp_char, post = split_at_orp(item.text)
        width = self.winfo_width()
        height = self.winfo_height()
        # Anchor ORP-x slightly left of dead-center so the eye doesn't
        # have to track a moving median when long words extend right.
        # ~38% from left is a common Spritz tuning value.
        orp_x = int(width * 0.38)
        y = height // 2

        orp_w = self._font.measure(orp_char) if orp_char else 0
        pre_anchor_x = orp_x - orp_w / 2
        post_anchor_x = orp_x + orp_w / 2

        if pre:
            self.create_text(pre_anchor_x, y, text=pre, anchor="e", font=self._font, fill=self._fg)
        if orp_char:
            self.create_text(
                orp_x,
                y,
                text=orp_char,
                anchor="center",
                font=self._font,
                fill=self._accent,
            )
        if post:
            self.create_text(
                post_anchor_x,
                y,
                text=post,
                anchor="w",
                font=self._font,
                fill=self._fg,
            )
