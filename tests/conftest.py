"""Shared fixtures: tiny factories for history files and corpora.

Everything is offline and deterministic; tests build their own history
files in ``tmp_path`` and never touch the real ``$HISTFILE``.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def write_file(tmp_path):
    """Write ``text`` to ``tmp_path/name`` and return the path as str."""

    def _write(name: str, text: str) -> str:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    return _write


@pytest.fixture
def repeated():
    """Build a command list with exact repetition counts.

    ``repeated(("git status", 12), ("ls", 2))`` -> list of 14 commands.
    Interleaved (round-robin) so ordering bugs can't hide behind sorted
    input.
    """

    def _build(*pairs):
        remaining = {cmd: count for cmd, count in pairs}
        out = []
        while any(remaining.values()):
            for cmd, _ in pairs:
                if remaining[cmd] > 0:
                    out.append(cmd)
                    remaining[cmd] -= 1
        return out

    return _build
