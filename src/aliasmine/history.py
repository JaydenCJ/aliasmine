"""Read shell history files: bash, zsh (plain and extended), and fish.

All parsers are deliberately lenient — real history files accumulate junk
(interrupted writes, mixed formats after a shell switch, editor artifacts)
and a miner that dies on line 48,213 of somebody's ``.zsh_history`` is
useless. Anything that does not parse as metadata is treated as a command.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from .errors import HistoryNotFoundError

#: A bash ``HISTTIMEFORMAT`` timestamp line: ``#1626161616``.
_BASH_TS_RE = re.compile(r"^#(\d{9,12})\s*$")

#: A zsh EXTENDED_HISTORY entry header: ``: 1626161616:0;git status``.
_ZSH_EXT_RE = re.compile(r"^: (\d+):(\d+);(.*)$")

#: A fish history command line: ``- cmd: git status``.
_FISH_CMD_RE = re.compile(r"^- cmd: (.*)$")

#: A fish history timestamp line: ``  when: 1626161616``.
_FISH_WHEN_RE = re.compile(r"^\s+when: (\d+)\s*$")

#: History file locations probed (in order) when no file is given.
DEFAULT_HISTORY_PATHS = (
    "~/.bash_history",
    "~/.zsh_history",
    "~/.local/share/fish/fish_history",
    "~/.history",
)


@dataclass(frozen=True)
class HistoryEntry:
    """One command as it was recorded by the shell."""

    command: str
    timestamp: Optional[int] = None
    duration: Optional[int] = None
    source: str = ""


def parse_bash(text: str, source: str = "") -> List[HistoryEntry]:
    """Parse plain bash history, honoring ``HISTTIMEFORMAT`` epoch comments.

    A line matching ``#<epoch>`` is a timestamp for the *next* command line;
    every other non-blank line is a command (including genuine ``#`` comments
    the user typed — they were keystrokes too, and the miner filters them).
    """
    entries: List[HistoryEntry] = []
    pending_ts: Optional[int] = None
    for line in text.splitlines():
        if not line.strip():
            continue
        match = _BASH_TS_RE.match(line)
        if match:
            pending_ts = int(match.group(1))
            continue
        entries.append(HistoryEntry(command=line.rstrip("\n"), timestamp=pending_ts, source=source))
        pending_ts = None
    return entries


def parse_zsh(text: str, source: str = "") -> List[HistoryEntry]:
    """Parse zsh history in EXTENDED_HISTORY format, with plain fallback.

    Extended entries look like ``: 1626161616:0;git status``. Multi-line
    commands are stored with a trailing backslash on every continued line;
    we stitch them back together. Lines that match neither pattern (a plain
    zsh history, or corruption) are kept as bare commands.
    """
    entries: List[HistoryEntry] = []
    current: Optional[Tuple[str, Optional[int], Optional[int]]] = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            body, ts, dur = current
            if body.strip():
                entries.append(
                    HistoryEntry(command=body, timestamp=ts, duration=dur, source=source)
                )
            current = None

    for line in text.splitlines():
        match = _ZSH_EXT_RE.match(line)
        if match:
            flush()
            current = (match.group(3), int(match.group(1)), int(match.group(2)))
        elif current is not None and current[0].endswith("\\"):
            # Continuation of a multi-line command: replace the trailing
            # backslash with a newline, as zsh itself does when reloading.
            body, ts, dur = current
            current = (body[:-1] + "\n" + line, ts, dur)
        else:
            flush()
            if line.strip():
                entries.append(HistoryEntry(command=line, source=source))
    flush()
    return entries


def _unescape_fish(value: str) -> str:
    """Undo fish's history escaping (``\\\\`` and ``\\n``)."""
    out: List[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_fish(text: str, source: str = "") -> List[HistoryEntry]:
    """Parse fish's YAML-flavoured history file.

    Only the ``- cmd:`` and ``when:`` keys matter; ``paths:`` blocks and
    anything else fish adds are skipped without complaint.
    """
    entries: List[HistoryEntry] = []
    for line in text.splitlines():
        cmd_match = _FISH_CMD_RE.match(line)
        if cmd_match:
            command = _unescape_fish(cmd_match.group(1))
            if command.strip():
                entries.append(HistoryEntry(command=command, source=source))
            continue
        when_match = _FISH_WHEN_RE.match(line)
        if when_match and entries:
            last = entries[-1]
            if last.timestamp is None:
                entries[-1] = HistoryEntry(
                    command=last.command,
                    timestamp=int(when_match.group(1)),
                    duration=last.duration,
                    source=last.source,
                )
    return entries


_PARSERS = {"bash": parse_bash, "zsh": parse_zsh, "fish": parse_fish}

#: Shell names accepted by the CLI's ``--shell`` option.
KNOWN_SHELLS = ("auto",) + tuple(sorted(_PARSERS))


def sniff_format(text: str, path: str = "") -> str:
    """Guess the history format from the filename, then the content.

    The filename wins for fish (its format is unambiguous anyway); otherwise
    the first 50 non-blank lines are checked for zsh/fish markers, and plain
    bash is the fallback — the bash parser accepts anything line-oriented.
    """
    name = os.path.basename(path)
    if "fish" in name:
        return "fish"
    checked = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        if _ZSH_EXT_RE.match(line):
            return "zsh"
        if _FISH_CMD_RE.match(line):
            return "fish"
        checked += 1
        if checked >= 50:
            break
    return "bash"


def parse_history(text: str, shell: str = "auto", source: str = "") -> Tuple[List[HistoryEntry], str]:
    """Parse ``text`` as history; returns ``(entries, detected_format)``."""
    fmt = sniff_format(text, source) if shell == "auto" else shell
    parser = _PARSERS.get(fmt)
    if parser is None:
        raise ValueError(f"unknown shell format: {fmt!r} (expected one of {', '.join(KNOWN_SHELLS)})")
    return parser(text, source=source), fmt


def read_history_file(path: str, shell: str = "auto") -> Tuple[List[HistoryEntry], str]:
    """Read and parse one history file (bytes decoded leniently)."""
    with open(path, "rb") as handle:
        raw = handle.read()
    # zsh "metafies" bytes >= 0x83 with a 0x83 marker; undo the common case
    # so multibyte commands round-trip instead of turning into mojibake.
    raw = _unmetafy(raw)
    text = raw.decode("utf-8", errors="replace")
    return parse_history(text, shell=shell, source=path)


def _unmetafy(raw: bytes) -> bytes:
    """Undo zsh metafication: ``0x83, b`` encodes the byte ``b ^ 0x20``."""
    if b"\x83" not in raw:
        return raw
    out = bytearray()
    i = 0
    while i < len(raw):
        byte = raw[i]
        if byte == 0x83 and i + 1 < len(raw):
            out.append(raw[i + 1] ^ 0x20)
            i += 2
        else:
            out.append(byte)
            i += 1
    return bytes(out)


def default_history_files() -> List[str]:
    """Locate history files to mine when none are named on the command line.

    ``$HISTFILE`` is honored first; the well-known per-shell locations are
    probed after it. Only files that exist are returned.
    """
    candidates: List[str] = []
    histfile = os.environ.get("HISTFILE")
    if histfile:
        candidates.append(histfile)
    candidates.extend(os.path.expanduser(p) for p in DEFAULT_HISTORY_PATHS)
    found: List[str] = []
    for path in candidates:
        if os.path.isfile(path) and path not in found:
            found.append(path)
    return found


def load_history(
    paths: Sequence[str], shell: str = "auto"
) -> Tuple[List[HistoryEntry], List[Tuple[str, str, int]]]:
    """Load one or more history files.

    Returns ``(entries, files)`` where ``files`` is a list of
    ``(path, detected_format, entry_count)`` tuples in input order.
    Raises :class:`HistoryNotFoundError` if ``paths`` is empty and nothing
    can be discovered, or if a named file does not exist.
    """
    resolved: Iterable[str] = paths or default_history_files()
    resolved = list(resolved)
    if not resolved:
        raise HistoryNotFoundError(
            "no history file found - pass one explicitly, e.g. `aliasmine scan ~/.zsh_history`"
        )
    entries: List[HistoryEntry] = []
    files: List[Tuple[str, str, int]] = []
    for path in resolved:
        if not os.path.isfile(path):
            raise HistoryNotFoundError(f"history file not found: {path}")
        file_entries, fmt = read_history_file(path, shell=shell)
        entries.extend(file_entries)
        files.append((path, fmt, len(file_entries)))
    return entries, files
