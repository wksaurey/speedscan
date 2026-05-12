"""Pure-logic tests for the ORP math in word_view.

Canvas rendering is not unit-tested — visual correctness is verified by
running the app. These tests cover the splitting and indexing rules so
a regression in the math gets caught even without a display.
"""

from __future__ import annotations

import pytest

from speedscan.ui.word_view import orp_index, split_at_orp


class TestOrpIndex:
    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("", 0),
            ("a", 0),
            ("at", 1),
            ("the", 1),
            ("hello", 1),
            ("mitochondria", 3),
            ("supercalifragilistic", 4),
        ],
    )
    def test_returns_expected_index(self, word: str, expected: int) -> None:
        assert orp_index(word) == expected

    def test_index_in_bounds_for_any_non_empty(self) -> None:
        for word in ["a", "to", "cell", "Spritz", "encyclopedia", "antidisestablishment"]:
            assert 0 <= orp_index(word) < len(word)


class TestSplitAtOrp:
    def test_empty_string(self) -> None:
        assert split_at_orp("") == ("", "", "")

    def test_single_char(self) -> None:
        assert split_at_orp("a") == ("", "a", "")

    def test_short_word(self) -> None:
        # "the": ORP at index 1 → ("t", "h", "e")
        assert split_at_orp("the") == ("t", "h", "e")

    def test_medium_word(self) -> None:
        # "hello": ORP at index 1 → ("h", "e", "llo")
        assert split_at_orp("hello") == ("h", "e", "llo")

    def test_long_word(self) -> None:
        # "mitochondria" (12 chars): ORP at index 3 → ("mit", "o", "chondria")
        assert split_at_orp("mitochondria") == ("mit", "o", "chondria")

    def test_recomposes_to_original(self) -> None:
        for word in ["a", "to", "cat", "spritz", "encyclopedia"]:
            pre, orp, post = split_at_orp(word)
            assert pre + orp + post == word
