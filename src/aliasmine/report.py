"""Render analyses as terminal reports, JSON, and shell config exports.

Rendering is pure string-building — no printing, no terminal probing —
so every report is testable byte-for-byte. Color is decided by the caller
(the CLI checks ``--color``, ``NO_COLOR``, and whether stdout is a TTY)
and passed in as a flag.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .mining import Candidate
from .pipeline import Analysis
from .savings import (
    DEFAULT_WPM,
    Suggestion,
    format_duration,
    format_int,
    pluralize,
    seconds_saved,
)

#: Width of the proportional bar in the scan table.
_BAR_WIDTH = 12

#: Longest command text shown before ellipsis in tables.
_CMD_WIDTH = 44


class Style:
    """Tiny ANSI styler; a disabled instance returns text unchanged."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\x1b[{code}m{text}\x1b[0m" if self.enabled else text

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)


def _clip(text: str, width: int = _CMD_WIDTH) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _bar(count: int, max_count: int, width: int = _BAR_WIDTH) -> str:
    if max_count <= 0:
        return ""
    filled = max(1, round(width * count / max_count))
    return "█" * filled


def render_scan(
    analysis: Analysis,
    files: Sequence[Tuple[str, str, int]],
    top: int = 15,
    wpm: int = DEFAULT_WPM,
    style: Optional[Style] = None,
) -> str:
    """The flagship report: what you retype, and what it costs you."""
    s = style or Style(False)
    lines: List[str] = []
    file_desc = ", ".join(f"{path} ({fmt})" for path, fmt, _ in files)
    lines.append(
        s.bold("aliasmine")
        + f" — mined {format_int(analysis.entries_total)} history entries from {file_desc}"
    )
    lines.append("")
    lines.append(f"  unique commands          {format_int(analysis.unique_commands):>8}")
    lines.append(f"  repeated long commands   {format_int(len(analysis.candidates)):>8}")
    lines.append(
        f"  keystrokes on repeats    {format_int(analysis.repeat_keystrokes):>8}"
    )
    lines.append("")

    shown = analysis.candidates[:top]
    if not shown:
        lines.append("No repeated long commands found — either your history is tiny")
        lines.append("or your aliases already cover everything. Try --min-count 2.")
        return "\n".join(lines) + "\n"

    max_count = max(c.count for c in shown)
    lines.append(f"  {'#':>2}  {'TIMES':>6}  {'COMMAND':<{_CMD_WIDTH}}  {'KEYSTROKES':>10}")
    for rank, cand in enumerate(shown, start=1):
        marker = "" if cand.kind == "exact" else " +"
        cmd = _clip(cand.command + marker)
        lines.append(
            f"  {rank:>2}  {s.cyan(f'{cand.count:>6,}')}  {cmd:<{_CMD_WIDTH}}  "
            f"{format_int(cand.count * len(cand.command)):>10}  "
            f"{s.green(_bar(cand.count, max_count))}"
        )
    if any(c.kind == "prefix" for c in shown):
        lines.append(s.dim("      + = a common stem; the arguments after it vary"))
    lines.append("")

    champion = analysis.candidates[0]
    champion_suggestion = next(
        (sg for sg in analysis.suggestions if sg.command == champion.command), None
    )
    headline = (
        f"You typed `{champion.command}` {s.bold(pluralize(champion.count, 'time'))}"
        f" — {format_int(champion.count * len(champion.command))} keystrokes."
    )
    if champion_suggestion is not None:
        headline += (
            f" Alias `{champion_suggestion.name}` would have saved "
            f"{format_int(champion_suggestion.total_saved)}."
        )
    lines.append(headline)

    for ignored in analysis.ignored_aliases[:3]:
        lines.append(
            s.yellow(
                f"You own alias `{ignored.name}` = `{ignored.expansion}` but typed it in full "
                f"{pluralize(ignored.typed_full, 'time')} ({pluralize(ignored.wasted_keystrokes, 'keystroke')} wasted)."
            )
        )

    if analysis.suggestions:
        total = analysis.total_saved
        lines.append("")
        lines.append(
            f"{pluralize(len(analysis.suggestions), 'alias')} proposed — "
            f"{format_int(total)} keystrokes (~{format_duration(seconds_saved(total, wpm))} "
            f"at {wpm} WPM). Run `aliasmine suggest` to see them."
        )
    return "\n".join(lines) + "\n"


def render_suggest(
    analysis: Analysis, wpm: int = DEFAULT_WPM, style: Optional[Style] = None
) -> str:
    """The proposal table: alias, expansion, evidence, and price tag."""
    s = style or Style(False)
    lines: List[str] = []
    if not analysis.suggestions:
        lines.append("Nothing to suggest — no repeated command cleared the thresholds.")
        lines.append("Lower them with --min-count / --min-length if that seems wrong.")
        return "\n".join(lines) + "\n"

    name_w = max(5, max(len(sg.name) for sg in analysis.suggestions))
    lines.append(
        f"  {'ALIAS':<{name_w}}  {'COMMAND':<{_CMD_WIDTH}}  {'TIMES':>6}  {'SAVES/USE':>9}  {'TOTAL':>8}"
    )
    for sg in analysis.suggestions:
        lines.append(
            f"  {s.bold(f'{sg.name:<{name_w}}')}  {_clip(sg.command):<{_CMD_WIDTH}}  "
            f"{sg.count:>6,}  {sg.saved_per_use:>9}  {s.green(f'{sg.total_saved:>8,}')}"
        )
    total = analysis.total_saved
    lines.append("")
    lines.append(
        f"{pluralize(len(analysis.suggestions), 'alias')} proposed — {format_int(total)} keystrokes saved "
        f"(~{format_duration(seconds_saved(total, wpm))} at {wpm} WPM)."
    )
    lines.append("Adopt them: aliasmine export --format zsh >> ~/.zshrc")
    return "\n".join(lines) + "\n"


_EXPORT_FORMATS = ("bash", "zsh", "fish")


def _sh_quote(text: str) -> str:
    """Single-quote for POSIX shells, splicing embedded single quotes."""
    return "'" + text.replace("'", "'\\''") + "'"


def _fish_quote(text: str) -> str:
    """Single-quote for fish, which escapes with a backslash instead."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render_export(suggestions: Sequence[Suggestion], fmt: str) -> str:
    """Emit ready-to-source shell config for the proposed aliases.

    bash/zsh get ``alias`` lines; fish gets ``abbr`` definitions, which are
    the idiomatic fish equivalent (they expand inline and stay readable in
    history). Output is deterministic — no timestamps — so exports diff
    cleanly in dotfile repos.
    """
    if fmt not in _EXPORT_FORMATS:
        raise ValueError(f"unknown export format: {fmt!r} (expected one of {', '.join(_EXPORT_FORMATS)})")
    total = sum(s.total_saved for s in suggestions)
    lines = [
        f"# aliasmine: {pluralize(len(suggestions), 'alias')}, "
        f"~{format_int(total)} keystrokes saved over your mined history",
    ]
    for sg in suggestions:
        if fmt == "fish":
            lines.append(f"abbr -a {sg.name} {_fish_quote(sg.command)}")
        else:
            lines.append(f"alias {sg.name}={_sh_quote(sg.command)}")
    return "\n".join(lines) + "\n"


def scan_to_dict(
    analysis: Analysis,
    files: Sequence[Tuple[str, str, int]],
    top: int = 15,
) -> Dict[str, object]:
    """JSON-ready structure for ``scan --json``."""
    return {
        "files": [
            {"path": path, "format": fmt, "entries": count} for path, fmt, count in files
        ],
        "entries": analysis.entries_total,
        "unique_commands": analysis.unique_commands,
        "repeated_long_commands": len(analysis.candidates),
        "repeat_keystrokes": analysis.repeat_keystrokes,
        "top": [_candidate_to_dict(c) for c in analysis.candidates[:top]],
        "ignored_aliases": [
            {
                "name": ig.name,
                "expansion": ig.expansion,
                "typed_full": ig.typed_full,
                "wasted_keystrokes": ig.wasted_keystrokes,
            }
            for ig in analysis.ignored_aliases
        ],
    }


def _candidate_to_dict(candidate: Candidate) -> Dict[str, object]:
    return {
        "command": candidate.command,
        "count": candidate.count,
        "kind": candidate.kind,
        "keystrokes": candidate.count * len(candidate.command),
    }


def suggest_to_dict(analysis: Analysis, wpm: int = DEFAULT_WPM) -> Dict[str, object]:
    """JSON-ready structure for ``suggest --json``."""
    total = analysis.total_saved
    return {
        "suggestions": [
            {
                "alias": sg.name,
                "command": sg.command,
                "count": sg.count,
                "charged_count": sg.effective_count,
                "kind": sg.kind,
                "saved_per_use": sg.saved_per_use,
                "total_saved": sg.total_saved,
            }
            for sg in analysis.suggestions
        ],
        "total_saved": total,
        "estimated_seconds_saved": round(seconds_saved(total, wpm), 1),
        "wpm": wpm,
    }
