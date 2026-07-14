"""The end-to-end analysis pipeline: history in, priced suggestions out.

This is the library entry point the CLI is a thin shell around. Everything
is pure given its inputs — same history, same result — which is what makes
the whole tool trivially testable offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .existing import IgnoredAlias, find_ignored_aliases
from .history import HistoryEntry
from .mining import (
    DEFAULT_DOMINANCE,
    DEFAULT_MIN_COUNT,
    DEFAULT_MIN_LENGTH,
    Candidate,
    mine,
    normalized_commands,
    repeat_keystrokes,
)
from .naming import assign_names, build_reserved
from .savings import Suggestion, total_savings


@dataclass
class Analysis:
    """Everything the reports need, computed in one pass."""

    entries_total: int
    commands: List[str]
    candidates: List[Candidate]
    suggestions: List[Suggestion]
    ignored_aliases: List[IgnoredAlias]
    aliases: Dict[str, str] = field(default_factory=dict)

    @property
    def unique_commands(self) -> int:
        return len(set(self.commands))

    @property
    def repeat_keystrokes(self) -> int:
        return repeat_keystrokes(self.candidates)

    @property
    def total_saved(self) -> int:
        return total_savings(self.suggestions)


def _covered_by_alias(command: str, aliases: Dict[str, str]) -> Optional[str]:
    """Name of an existing alias that already covers ``command``, if any."""
    for name in sorted(aliases):
        expansion = aliases[name]
        if expansion and (command == expansion or command.startswith(expansion + " ")):
            return name
    return None


def _extends(longer: str, shorter: str) -> bool:
    return longer.startswith(shorter + " ")


def _charge_overlaps(suggestions: List[Suggestion]) -> List[Suggestion]:
    """Charge overlapping stem/child suggestions honestly.

    When both ``npm run`` and ``npm run dev`` are proposed, the 152 uses of
    ``npm run dev`` are charged to its own alias only — the stem keeps them
    as evidence (``count``) but not in its savings. A stem whose every use
    is covered by more specific suggestions prices at zero and is dropped:
    it would add nothing you could measure.
    """
    charged: List[Suggestion] = []
    for sg in suggestions:
        remaining = sg.count
        for other in suggestions:
            if other is sg or not _extends(other.command, sg.command):
                continue
            # Skip if an intermediate suggestion sits between the two —
            # its own subtraction already includes `other`'s uses.
            if any(
                third is not other
                and _extends(third.command, sg.command)
                and _extends(other.command, third.command)
                for third in suggestions
            ):
                continue
            remaining -= other.count
        remaining = max(remaining, 0)
        if remaining == 0:
            continue
        charged.append(
            Suggestion(
                name=sg.name,
                command=sg.command,
                count=sg.count,
                kind=sg.kind,
                charged_count=None if remaining == sg.count else remaining,
            )
        )
    return charged


def analyze(
    entries: Sequence[HistoryEntry],
    aliases: Optional[Dict[str, str]] = None,
    min_count: int = DEFAULT_MIN_COUNT,
    min_length: int = DEFAULT_MIN_LENGTH,
    dominance: float = DEFAULT_DOMINANCE,
    max_suggestions: int = 20,
) -> Analysis:
    """Run the full pipeline over parsed history entries.

    Candidates already covered by an existing alias are excluded from the
    suggestion list (they show up in the ignored-alias section instead —
    the user needs a habit change there, not a second alias).
    """
    aliases = aliases or {}
    commands = normalized_commands(entries)
    candidates = mine(
        commands, min_count=min_count, min_length=min_length, dominance=dominance
    )

    uncovered: List[Candidate] = [
        c for c in candidates if _covered_by_alias(c.command, aliases) is None
    ]

    reserved = build_reserved(commands, existing_aliases=aliases)
    to_name: List[Tuple[Tuple[str, ...], str]] = [
        (c.tokens, c.command) for c in uncovered
    ]
    names = assign_names(to_name, reserved)

    suggestions: List[Suggestion] = []
    for candidate, name in zip(uncovered, names):
        if name is None:
            continue
        suggestions.append(
            Suggestion(
                name=name,
                command=candidate.command,
                count=candidate.count,
                kind=candidate.kind,
            )
        )
        if len(suggestions) >= max_suggestions:
            break

    suggestions = _charge_overlaps(suggestions)

    ignored = find_ignored_aliases(aliases, commands, min_count=min(3, min_count))

    return Analysis(
        entries_total=len(list(entries)),
        commands=commands,
        candidates=candidates,
        suggestions=suggestions,
        ignored_aliases=ignored,
        aliases=aliases,
    )
