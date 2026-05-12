"""Tests for RsvpEngine — transport, navigation, events, WPM.

Engine is pure logic; these tests never touch a GUI or a real timer.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from speedscan.engine import EngineState, RsvpEngine
from speedscan.sources.base import LineLocation, PageLocation, TextItem


def _sample_items() -> list[TextItem]:
    """Mixed Page- and LineLocation items so seek-by-location is meaningful."""
    return [
        TextItem(text="alpha", location=PageLocation(page=1)),
        TextItem(text="beta", location=PageLocation(page=1)),
        TextItem(text="gamma", location=PageLocation(page=2)),
        TextItem(text="delta", location=LineLocation(line=10)),
        TextItem(text="epsilon", location=LineLocation(line=11)),
    ]


class TestInitialState:
    def test_paused_when_items_present(self) -> None:
        engine = RsvpEngine(_sample_items())
        assert engine.state is EngineState.PAUSED

    def test_idle_when_items_empty(self) -> None:
        engine = RsvpEngine([])
        assert engine.state is EngineState.IDLE

    def test_starts_at_index_zero(self) -> None:
        engine = RsvpEngine(_sample_items())
        assert engine.current_index == 0

    def test_current_item_none_when_empty(self) -> None:
        engine = RsvpEngine([])
        assert engine.current_item is None

    def test_current_item_is_first_when_populated(self) -> None:
        items = _sample_items()
        engine = RsvpEngine(items)
        assert engine.current_item == items[0]


class TestPlayPause:
    def test_play_transitions_paused_to_playing(self) -> None:
        engine = RsvpEngine(_sample_items())
        states: list[EngineState] = []
        engine.subscribe_on_state_change(states.append)

        engine.play()

        assert engine.state is EngineState.PLAYING
        assert states == [EngineState.PLAYING]

    def test_pause_transitions_playing_to_paused(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.play()
        states: list[EngineState] = []
        engine.subscribe_on_state_change(states.append)

        engine.pause()

        assert engine.state is EngineState.PAUSED
        assert states == [EngineState.PAUSED]

    def test_play_when_already_playing_does_not_fire_event(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.play()
        states: list[EngineState] = []
        engine.subscribe_on_state_change(states.append)

        engine.play()

        assert states == []

    def test_play_is_noop_when_idle(self) -> None:
        engine = RsvpEngine([])
        states: list[EngineState] = []
        engine.subscribe_on_state_change(states.append)

        engine.play()

        assert engine.state is EngineState.IDLE
        assert states == []


class TestStep:
    def test_forward_step_advances_index(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.step(1)
        assert engine.current_index == 1

    def test_forward_step_fires_on_display_with_new_item(self) -> None:
        items = _sample_items()
        engine = RsvpEngine(items)
        displayed: list[TextItem] = []
        engine.subscribe_on_display(displayed.append)

        engine.step(1)

        assert displayed == [items[1]]

    def test_backward_step_retreats(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.seek_to_index(3)
        engine.step(-1)
        assert engine.current_index == 2

    def test_backward_step_clamps_at_zero(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.step(-1)
        assert engine.current_index == 0

    def test_step_does_not_fire_when_clamped_with_no_movement(self) -> None:
        engine = RsvpEngine(_sample_items())
        displayed: list[TextItem] = []
        engine.subscribe_on_display(displayed.append)

        engine.step(-5)

        assert displayed == []

    def test_forward_step_clamps_at_last_index(self) -> None:
        items = _sample_items()
        engine = RsvpEngine(items)
        engine.step(999)
        assert engine.current_index == len(items) - 1

    def test_step_on_empty_is_noop(self) -> None:
        engine = RsvpEngine([])
        engine.step(1)
        assert engine.current_index == 0


class TestSeekToIndex:
    def test_valid_index_updates_position(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.seek_to_index(3)
        assert engine.current_index == 3

    def test_valid_index_fires_on_display(self) -> None:
        items = _sample_items()
        engine = RsvpEngine(items)
        displayed: list[TextItem] = []
        engine.subscribe_on_display(displayed.append)

        engine.seek_to_index(2)

        assert displayed == [items[2]]

    def test_negative_index_raises(self) -> None:
        engine = RsvpEngine(_sample_items())
        with pytest.raises(ValueError):
            engine.seek_to_index(-1)

    def test_out_of_range_raises(self) -> None:
        engine = RsvpEngine(_sample_items())
        with pytest.raises(ValueError):
            engine.seek_to_index(999)

    def test_seek_to_same_index_does_not_fire(self) -> None:
        engine = RsvpEngine(_sample_items())
        displayed: list[TextItem] = []
        engine.subscribe_on_display(displayed.append)

        engine.seek_to_index(0)

        assert displayed == []


class TestSeekToLocation:
    def test_finds_first_matching_page(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.seek_to_location(PageLocation(page=2))
        assert engine.current_index == 2

    def test_finds_first_matching_line(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.seek_to_location(LineLocation(line=11))
        assert engine.current_index == 4

    def test_fires_on_display_for_match(self) -> None:
        items = _sample_items()
        engine = RsvpEngine(items)
        displayed: list[TextItem] = []
        engine.subscribe_on_display(displayed.append)

        engine.seek_to_location(LineLocation(line=10))

        assert displayed == [items[3]]

    def test_raises_when_no_match(self) -> None:
        engine = RsvpEngine(_sample_items())
        with pytest.raises(ValueError):
            engine.seek_to_location(PageLocation(page=999))


class TestWpm:
    def test_default_wpm_yields_expected_delay(self) -> None:
        engine = RsvpEngine(_sample_items())
        # 60000 // 400 = 150 ms/word
        assert engine.current_word_delay_ms == 150

    def test_set_wpm_updates_delay(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.set_wpm(600)
        assert engine.wpm == 600
        assert engine.current_word_delay_ms == 100

    def test_wpm_clamped_to_minimum(self) -> None:
        engine = RsvpEngine(_sample_items(), wpm=50)
        assert engine.wpm == 100

    def test_wpm_clamped_to_maximum(self) -> None:
        engine = RsvpEngine(_sample_items(), wpm=5000)
        assert engine.wpm == 1500

    def test_set_wpm_clamps_below_minimum(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.set_wpm(10)
        assert engine.wpm == 100

    def test_set_wpm_clamps_above_maximum(self) -> None:
        engine = RsvpEngine(_sample_items())
        engine.set_wpm(9999)
        assert engine.wpm == 1500


class TestMultipleSubscribers:
    def test_all_display_subscribers_receive_event(self) -> None:
        items = _sample_items()
        engine = RsvpEngine(items)
        received_a: list[TextItem] = []
        received_b: list[TextItem] = []
        engine.subscribe_on_display(received_a.append)
        engine.subscribe_on_display(received_b.append)

        engine.step(1)

        assert received_a == [items[1]]
        assert received_b == [items[1]]

    def test_all_state_subscribers_receive_event(self) -> None:
        engine = RsvpEngine(_sample_items())
        received_a: list[EngineState] = []
        received_b: list[EngineState] = []
        engine.subscribe_on_state_change(received_a.append)
        engine.subscribe_on_state_change(received_b.append)

        engine.play()

        assert received_a == [EngineState.PLAYING]
        assert received_b == [EngineState.PLAYING]


class TestNoGuiImports:
    """Engine layering: no UI library leaks into pure logic.

    Parses engine.py with `ast` and walks every Import / ImportFrom node
    to prove the source text contains no `tkinter` or `customtkinter`
    references — a string check would catch comments too, but parsing
    is more precise and still rejects the imports we actually care about.
    """

    def _engine_source(self) -> str:
        # Locate engine.py relative to this test file so the check works
        # regardless of pytest's cwd.
        engine_path = Path(__file__).parent.parent / "src" / "speedscan" / "engine.py"
        return engine_path.read_text(encoding="utf-8")

    def test_no_tkinter_imports_in_ast(self) -> None:
        tree = ast.parse(self._engine_source())
        forbidden = {"tkinter", "customtkinter"}
        offending: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in forbidden:
                        offending.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                root = module.split(".", 1)[0]
                if root in forbidden:
                    offending.append(module)
        assert offending == []
