# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
"""customtkinter app — the renderer that ties everything together.

The app owns the engine, hosts the WordView, drives advancement via
Tk's `after()` based on `engine.current_word_delay_ms`, and translates
keystrokes into engine method calls.

customtkinter ships without type stubs; pyright would flag every
widget call as Unknown. Strict mode is preserved elsewhere; this
module opts out of the two affected rules to keep the rest of the
suite honest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import customtkinter as ctk

from speedscan.engine import EngineState, RsvpEngine
from speedscan.sources.base import LocationMarker, PageLocation, TextItem
from speedscan.ui.word_view import WordView

_WPM_STEP = 25


@dataclass(frozen=True, slots=True)
class DocumentInfo:
    """Document-level facts the renderer needs but the engine doesn't own.

    Computed once by the CLI when the file is loaded, then passed in.
    Keeps the engine's responsibility tight (transport + index).
    """

    title: str
    total_items: int
    max_page: int  # 0 if document has no page-based locations


def _format_location(loc: LocationMarker, max_page: int) -> str:
    if isinstance(loc, PageLocation):
        return f"p. {loc.page} of {max_page}" if max_page else f"p. {loc.page}"
    return f"line {loc.line}"


class SpeedScanApp(ctk.CTk):
    """Top-level customtkinter window."""

    def __init__(
        self,
        engine: RsvpEngine,
        doc: DocumentInfo,
        *,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.title(f"SpeedScan — {doc.title}")
        self.geometry("720x480")

        self._engine = engine
        self._doc = doc
        self._on_quit = on_quit
        self._tick_after_id: str | None = None

        self._build_layout()
        self._bind_keys()

        engine.subscribe_on_display(self._on_engine_display)
        engine.subscribe_on_state_change(self._on_engine_state_change)

        current = engine.current_item
        if current is not None:
            self._render_item(current)
        self._refresh_status_bar()

        self.protocol("WM_DELETE_WINDOW", self._quit)

        # Some X11 WMs don't auto-focus a newly mapped Tk window, so the
        # keybindings on `self` never fire until the user clicks the
        # window. Defer focus_force until after the window is mapped.
        self.after(50, self.focus_force)

    # -- layout ----------------------------------------------------------

    def _build_layout(self) -> None:
        self._word_view = WordView(self)
        self._word_view.pack(fill="both", expand=True)

        self._location_label = ctk.CTkLabel(self, text="", font=("Courier", 14))
        self._location_label.pack(pady=(0, 8))

        status = ctk.CTkFrame(self)
        status.pack(fill="x", side="bottom")
        self._status_label = ctk.CTkLabel(status, text="", anchor="w")
        self._status_label.pack(side="left", padx=8, pady=4)

    # -- engine event handlers ------------------------------------------

    def _on_engine_display(self, item: TextItem) -> None:
        self._render_item(item)
        self._refresh_status_bar()

    def _on_engine_state_change(self, state: EngineState) -> None:
        if state == EngineState.PLAYING:
            self._schedule_tick()
        else:
            self._cancel_tick()
        self._refresh_status_bar()

    # -- ticker ----------------------------------------------------------

    def _schedule_tick(self) -> None:
        self._cancel_tick()
        delay = self._engine.current_word_delay_ms
        self._tick_after_id = self.after(delay, self._tick)

    def _cancel_tick(self) -> None:
        if self._tick_after_id is not None:
            self.after_cancel(self._tick_after_id)
            self._tick_after_id = None

    def _tick(self) -> None:
        if self._engine.state != EngineState.PLAYING:
            return
        if self._engine.current_index + 1 >= self._doc.total_items:
            self._engine.pause()
            return
        self._engine.step(1)
        self._schedule_tick()

    # -- keybindings -----------------------------------------------------

    def _bind_keys(self) -> None:
        self.bind("<space>", lambda _e: self._toggle_play())
        self.bind("<Right>", lambda _e: self._engine.step(1))
        self.bind("<Left>", lambda _e: self._engine.step(-1))
        self.bind("<Up>", lambda _e: self._bump_wpm(+_WPM_STEP))
        self.bind("<Down>", lambda _e: self._bump_wpm(-_WPM_STEP))
        self.bind("<Control-q>", lambda _e: self._quit())

    def _toggle_play(self) -> None:
        if self._engine.state == EngineState.PLAYING:
            self._engine.pause()
        else:
            self._engine.play()

    def _bump_wpm(self, delta: int) -> None:
        self._engine.set_wpm(self._engine.wpm + delta)
        if self._engine.state == EngineState.PLAYING:
            self._schedule_tick()
        self._refresh_status_bar()

    # -- rendering -------------------------------------------------------

    def _render_item(self, item: TextItem) -> None:
        self._word_view.display(item)
        self._location_label.configure(text=_format_location(item.location, self._doc.max_page))

    def _refresh_status_bar(self) -> None:
        state = self._engine.state
        play_icon = "▶" if state == EngineState.PLAYING else "⏸"
        idx = self._engine.current_index
        total = self._doc.total_items
        pct = 0 if total == 0 else int(100 * (idx + 1) / total)
        self._status_label.configure(text=f"{play_icon}  {self._engine.wpm} wpm   {pct}%")

    # -- lifecycle -------------------------------------------------------

    def _quit(self) -> None:
        self._cancel_tick()
        if self._on_quit is not None:
            self._on_quit()
        self.destroy()


def run(
    engine: RsvpEngine,
    doc: DocumentInfo,
    *,
    on_quit: Callable[[], None] | None = None,
) -> None:
    """Construct the app and start the Tk mainloop."""
    app = SpeedScanApp(engine, doc, on_quit=on_quit)
    app.mainloop()


__all__ = ["DocumentInfo", "SpeedScanApp", "run"]
