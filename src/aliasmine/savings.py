"""Quantify what an alias is worth: keystrokes, and the time they cost.

The keystroke number is exact arithmetic over the mined counts. The time
figure is an honest estimate: characters divided by a typing speed that
defaults to 5 characters per second (~60 words per minute) and is
adjustable with ``--wpm``. No wall clock is ever read — everything here is
pure and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

#: Characters per "word" in the standard WPM definition.
_CHARS_PER_WORD = 5.0

#: Default typing speed used for time estimates.
DEFAULT_WPM = 60


def chars_per_second(wpm: int = DEFAULT_WPM) -> float:
    """Convert words-per-minute to characters-per-second."""
    if wpm <= 0:
        raise ValueError("wpm must be positive")
    return wpm * _CHARS_PER_WORD / 60.0


@dataclass(frozen=True)
class Suggestion:
    """A fully-priced alias proposal, ready to render or export.

    ``count`` is the evidence — how often the command (or stem) was typed.
    ``charged_count`` is what the alias is billed for: uses already covered
    by a more specific sibling suggestion are charged there instead, so the
    grand total never double-counts a keystroke. ``None`` means no overlap.
    """

    name: str
    command: str
    count: int
    kind: str  # "exact" or "prefix"
    charged_count: Optional[int] = None

    @property
    def effective_count(self) -> int:
        return self.count if self.charged_count is None else self.charged_count

    @property
    def saved_per_use(self) -> int:
        """Keystrokes saved every time the alias is used instead."""
        return max(len(self.command) - len(self.name), 0)

    @property
    def total_saved(self) -> int:
        """Keystrokes this alias would have saved over the mined history."""
        return self.effective_count * self.saved_per_use


def total_savings(suggestions: Sequence[Suggestion]) -> int:
    """Sum of keystrokes saved across all suggestions."""
    return sum(s.total_saved for s in suggestions)


def seconds_saved(keystrokes: int, wpm: int = DEFAULT_WPM) -> float:
    """Estimated typing time represented by ``keystrokes``."""
    return keystrokes / chars_per_second(wpm)


def format_duration(seconds: float) -> str:
    """Render seconds as a compact human duration: ``48s``, ``12m``, ``2h 05m``.

    Below a minute we keep seconds; below an hour, whole minutes; above,
    hours and zero-padded minutes. Rounding is half-up on the displayed
    unit so the string never claims more than ~30s of false precision.
    """
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, _ = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 48:
        return f"{hours}h {minutes:02d}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def format_int(value: int) -> str:
    """Thousands-separated integer: ``48213`` -> ``48,213``."""
    return f"{value:,}"


def pluralize(count: int, noun: str) -> str:
    """Count + correctly-inflected noun: ``1 alias``, ``18 aliases``.

    Nouns ending in ``s`` take ``es``; everything the reports pluralize is
    regular, so no irregular table is needed.
    """
    suffix = "" if count == 1 else ("es" if noun.endswith("s") else "s")
    return f"{format_int(count)} {noun}{suffix}"
