"""Resume-position and recent-files persistence.

Stores per-file reading position keyed by content hash so renames don't
lose resume state. Also tracks the recently-opened files list backing
the idle screen (design §F7).

State lives in a single `state.json` so the file picker and resume
logic share one source of truth.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

_STATE_FORMAT_VERSION = 1


def default_config_dir() -> Path:
    """Resolve XDG config directory for SpeedScan.

    Honors `$XDG_CONFIG_HOME` when set, otherwise `~/.config/speedscan`.
    """
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "speedscan"


@dataclass(frozen=True, slots=True)
class RecentFile:
    path: Path
    file_hash: str
    position: int
    last_opened: datetime


class Persistence:
    """Resume positions + recent-files list, persisted to `state.json`.

    Caller provides the config directory; the CLI wires
    `default_config_dir()` at startup. Tests pass `tmp_path`.
    """

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self._state_path = config_dir / "state.json"

    def save_position(self, file_hash: str, file_path: Path, position: int) -> None:
        """Record reading position and bump the file's last-opened time."""
        state = self._load_state()
        state[file_hash] = {
            "path": str(file_path),
            "position": position,
            "last_opened": datetime.now(UTC).isoformat(),
        }
        self._write_state(state)

    def load_position(self, file_hash: str) -> int | None:
        """Return saved position for `file_hash`, or None if unknown."""
        entry = self._load_state().get(file_hash)
        if entry is None:
            return None
        return int(entry["position"])

    def recent_files(self, limit: int = 10) -> list[RecentFile]:
        """Return up to `limit` files, most-recently-opened first."""
        state = self._load_state()
        files: list[RecentFile] = []
        for file_hash, entry in state.items():
            try:
                files.append(
                    RecentFile(
                        path=Path(entry["path"]),
                        file_hash=file_hash,
                        position=int(entry["position"]),
                        last_opened=datetime.fromisoformat(entry["last_opened"]),
                    )
                )
            except (KeyError, ValueError, TypeError):
                # Skip malformed individual entries rather than failing
                # the whole list — a corrupt entry shouldn't hide the
                # rest of the user's recents.
                continue
        files.sort(key=lambda f: f.last_opened, reverse=True)
        return files[:limit]

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {}
        try:
            with self._state_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if payload.get("version") != _STATE_FORMAT_VERSION:
                return {}
            files = payload.get("files")
            if not isinstance(files, dict):
                return {}
            return cast(dict[str, Any], files)
        except (json.JSONDecodeError, OSError):
            # Treat a corrupt state file as empty rather than crashing
            # at startup — user loses recents, not the app.
            return {}

    def _write_state(self, files: dict[str, Any]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        payload = {"version": _STATE_FORMAT_VERSION, "files": files}
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.config_dir,
            prefix="state.",
            suffix=".tmp",
            delete=False,
        ) as f:
            json.dump(payload, f)
            tmp_name = f.name
        os.replace(tmp_name, self._state_path)
