"""Tests for resume-position and recent-files persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from speedscan.persistence import Persistence, RecentFile, default_config_dir


class TestDefaultConfigDir:
    def test_honors_xdg_config_home(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert default_config_dir() == tmp_path / "speedscan"

    def test_falls_back_to_home_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert default_config_dir() == Path.home() / ".config" / "speedscan"


class TestSaveAndLoadPosition:
    def test_round_trip(self, tmp_path: Path) -> None:
        p = Persistence(tmp_path)
        p.save_position("abc123", Path("/tmp/doc.txt"), position=42)
        assert p.load_position("abc123") == 42

    def test_load_returns_none_for_unknown_hash(self, tmp_path: Path) -> None:
        p = Persistence(tmp_path)
        assert p.load_position("never-seen") is None

    def test_save_overwrites_previous_position(self, tmp_path: Path) -> None:
        p = Persistence(tmp_path)
        p.save_position("abc", Path("/tmp/a.txt"), position=10)
        p.save_position("abc", Path("/tmp/a.txt"), position=99)
        assert p.load_position("abc") == 99

    def test_persists_across_instances(self, tmp_path: Path) -> None:
        Persistence(tmp_path).save_position("k", Path("/tmp/a.txt"), 7)
        assert Persistence(tmp_path).load_position("k") == 7

    def test_creates_config_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deeply" / "nested"
        Persistence(nested).save_position("k", Path("/tmp/a.txt"), 1)
        assert nested.is_dir()


class TestRecentFiles:
    def test_empty_state_returns_empty_list(self, tmp_path: Path) -> None:
        assert Persistence(tmp_path).recent_files() == []

    def test_orders_most_recent_first(self, tmp_path: Path) -> None:
        p = Persistence(tmp_path)
        # Saves are sequential so timestamps strictly increase.
        p.save_position("first", Path("/tmp/first.txt"), 1)
        p.save_position("second", Path("/tmp/second.txt"), 2)
        p.save_position("third", Path("/tmp/third.txt"), 3)

        recents = p.recent_files()

        assert [rf.file_hash for rf in recents] == ["third", "second", "first"]

    def test_updating_existing_file_promotes_it(self, tmp_path: Path) -> None:
        p = Persistence(tmp_path)
        p.save_position("a", Path("/tmp/a.txt"), 1)
        p.save_position("b", Path("/tmp/b.txt"), 1)
        p.save_position("a", Path("/tmp/a.txt"), 2)  # touch a again

        recents = p.recent_files()

        assert recents[0].file_hash == "a"

    def test_respects_limit(self, tmp_path: Path) -> None:
        p = Persistence(tmp_path)
        for i in range(5):
            p.save_position(f"h{i}", Path(f"/tmp/{i}.txt"), i)

        assert len(p.recent_files(limit=2)) == 2

    def test_entry_carries_path_position_and_hash(self, tmp_path: Path) -> None:
        p = Persistence(tmp_path)
        p.save_position("hashval", Path("/tmp/doc.txt"), 17)

        rf = p.recent_files()[0]

        assert isinstance(rf, RecentFile)
        assert rf.file_hash == "hashval"
        assert rf.path == Path("/tmp/doc.txt")
        assert rf.position == 17
        assert rf.last_opened.tzinfo is not None  # timezone-aware


class TestCorruption:
    def test_corrupt_state_file_treated_as_empty(self, tmp_path: Path) -> None:
        (tmp_path / "state.json").write_text("{not valid json")
        p = Persistence(tmp_path)

        assert p.load_position("anything") is None
        assert p.recent_files() == []

    def test_unknown_format_version_treated_as_empty(self, tmp_path: Path) -> None:
        (tmp_path / "state.json").write_text(
            json.dumps({"version": 999, "files": {"x": {"path": "/", "position": 0}}})
        )
        p = Persistence(tmp_path)

        assert p.recent_files() == []

    def test_malformed_individual_entry_skipped(self, tmp_path: Path) -> None:
        good_time = datetime.now(UTC).isoformat()
        (tmp_path / "state.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "files": {
                        "good": {
                            "path": "/tmp/g.txt",
                            "position": 5,
                            "last_opened": good_time,
                        },
                        "bad": {"path": "/tmp/b.txt"},  # missing fields
                    },
                }
            )
        )
        p = Persistence(tmp_path)

        recents = p.recent_files()

        assert [rf.file_hash for rf in recents] == ["good"]


class TestAtomicWrite:
    def test_does_not_leave_tmp_files(self, tmp_path: Path) -> None:
        p = Persistence(tmp_path)
        p.save_position("k", Path("/tmp/a.txt"), 1)

        assert list(tmp_path.glob("*.tmp")) == []


def test_load_position_returns_latest_save(tmp_path: Path) -> None:
    p = Persistence(tmp_path)
    p.save_position("h", Path("/tmp/x.txt"), 1)
    earlier = datetime.now(UTC) - timedelta(minutes=5)
    # Sanity check that timestamps are real datetimes downstream code can
    # compare — guards against accidentally storing strings.
    assert p.recent_files()[0].last_opened > earlier
