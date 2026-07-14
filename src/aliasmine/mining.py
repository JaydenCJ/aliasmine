"""Mine normalized commands for alias-worthy repetition.

Two kinds of habit are worth an alias:

* **exact** — the same full command typed over and over (``git status``);
* **prefix** — a stable stem with varying tails (``git commit -m "..."``).

Prefix mining counts every token-prefix of every command, then prunes with
a *dominant-child* rule: if 90 % of the time ``git commit`` continues as
``git commit -m``, the shorter stem is dropped and the longer one proposed —
that is the alias the fingers actually want.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .history import HistoryEntry
from .normalize import head_command, is_minable, normalize, split_tokens

#: Assumed alias length when ranking candidates before names are assigned.
ASSUMED_ALIAS_LEN = 2

#: Default knobs, shared with the CLI so ``--help`` and docs agree.
DEFAULT_MIN_COUNT = 5
DEFAULT_MIN_LENGTH = 6
DEFAULT_DOMINANCE = 0.9


@dataclass(frozen=True)
class Candidate:
    """A repeated command (or command stem) worth aliasing."""

    command: str
    tokens: Tuple[str, ...]
    count: int
    exact_count: int

    @property
    def kind(self) -> str:
        """``exact`` if every occurrence was the full command, else ``prefix``."""
        return "exact" if self.exact_count == self.count else "prefix"

    @property
    def potential(self) -> int:
        """Keystrokes reclaimable assuming a short alias — the ranking key."""
        return self.count * max(len(self.command) - ASSUMED_ALIAS_LEN, 0)


def normalized_commands(entries: Iterable[HistoryEntry]) -> List[str]:
    """Normalize entries and drop lines that can never be aliased."""
    commands: List[str] = []
    for entry in entries:
        if not is_minable(entry.command):
            continue
        norm = normalize(entry.command)
        if norm:
            commands.append(norm)
    return commands


def mine(
    commands: Sequence[str],
    min_count: int = DEFAULT_MIN_COUNT,
    min_length: int = DEFAULT_MIN_LENGTH,
    dominance: float = DEFAULT_DOMINANCE,
) -> List[Candidate]:
    """Return alias candidates from normalized commands, best first.

    ``min_count``   — occurrences below this are not a habit, just history.
    ``min_length``  — commands shorter than this save nothing worth having.
    ``dominance``   — a stem is dropped when one single-token extension
                      accounts for at least this fraction of its uses.
    Ordering is fully deterministic: potential savings desc, then count
    desc, then command text asc.
    """
    exact_counts: Counter = Counter(commands)
    prefix_counts: Counter = Counter()
    for command in commands:
        tokens = tuple(split_tokens(command))
        for k in range(1, len(tokens) + 1):
            prefix_counts[tokens[:k]] += 1

    eligible: Dict[Tuple[str, ...], int] = {
        prefix: count
        for prefix, count in prefix_counts.items()
        if count >= min_count and len(" ".join(prefix)) >= min_length
    }

    survivors: List[Candidate] = []
    for prefix, count in eligible.items():
        if _has_dominant_child(prefix, count, eligible, dominance):
            continue
        command = " ".join(prefix)
        survivors.append(
            Candidate(
                command=command,
                tokens=prefix,
                count=count,
                exact_count=exact_counts.get(command, 0),
            )
        )

    survivors.sort(key=lambda c: (-c.potential, -c.count, c.command))
    return survivors


def _has_dominant_child(
    prefix: Tuple[str, ...],
    count: int,
    eligible: Dict[Tuple[str, ...], int],
    dominance: float,
) -> bool:
    """True when one eligible one-token extension absorbs ``prefix``.

    If almost every ``docker compose`` you typed was ``docker compose up``,
    an alias for the stem would still leave you typing ``up`` — propose the
    longer command instead and keep the report free of near-duplicates.
    """
    depth = len(prefix)
    for other, other_count in eligible.items():
        if len(other) != depth + 1 or other[:depth] != prefix:
            continue
        if other_count >= dominance * count:
            return True
    return False


@dataclass(frozen=True)
class CorpusStats:
    """Aggregate statistics over a whole history corpus."""

    total_entries: int
    minable_commands: int
    unique_commands: int
    total_keystrokes: int
    avg_length: float
    top_programs: Tuple[Tuple[str, int], ...]


def corpus_stats(entries: Sequence[HistoryEntry], top_programs: int = 10) -> CorpusStats:
    """Compute the numbers behind ``aliasmine stats``."""
    commands = normalized_commands(entries)
    unique = len(set(commands))
    keystrokes = sum(len(c) for c in commands)
    heads: Counter = Counter()
    for command in commands:
        head = head_command(split_tokens(command))
        if head:
            heads[head] += 1
    ranked = sorted(heads.items(), key=lambda item: (-item[1], item[0]))[:top_programs]
    return CorpusStats(
        total_entries=len(list(entries)),
        minable_commands=len(commands),
        unique_commands=unique,
        total_keystrokes=keystrokes,
        avg_length=(keystrokes / len(commands)) if commands else 0.0,
        top_programs=tuple(ranked),
    )


def repeat_keystrokes(candidates: Sequence[Candidate]) -> int:
    """Total keystrokes spent on the surviving repeated commands.

    Candidates overlap: every ``npm run dev`` is also inside the count of
    the ``npm run`` stem. Each occurrence is therefore charged to the most
    specific candidate that covers it (the same rule suggestion pricing
    uses), so this headline never exceeds the corpus keystroke total.
    """
    charged: Dict[Tuple[str, ...], int] = {c.tokens: c.count for c in candidates}
    for cand in candidates:
        # Walk up the token prefixes to the nearest surviving ancestor and
        # move this candidate's occurrences out of its count.
        for depth in range(len(cand.tokens) - 1, 0, -1):
            ancestor = cand.tokens[:depth]
            if ancestor in charged:
                charged[ancestor] -= cand.count
                break
    return sum(max(charged[c.tokens], 0) * len(c.command) for c in candidates)
