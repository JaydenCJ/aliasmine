"""Parse the aliases a user already has, and find the ones they ignore.

Sources accepted: bash/zsh rc files or the output of the ``alias`` builtin
(``alias gs='git status'``), fish function-style aliases
(``alias gs 'git status'``), and fish abbreviations
(``abbr -a gs 'git status'``). Everything else in the file is ignored, so
pointing aliasmine at a whole ``.zshrc`` just works.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence

from .normalize import normalize, split_tokens

#: ``name=value`` inside a bash/zsh alias statement.
_ASSIGN_RE = re.compile(r"^([A-Za-z0-9_.:@%+-]+)=(.*)$", re.DOTALL)

#: Flags of ``abbr`` that take no argument and can precede the name.
_ABBR_BARE_FLAGS = {"-a", "--add", "-g", "--global", "-U", "--universal"}


def _unquote(value: str) -> str:
    """Strip one layer of shell quoting from an alias expansion."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        inner = value[1:-1]
        if value[0] == "'":
            # POSIX '\'' splicing: alias x='git '\''s'\'' ' — rare, best effort.
            return inner.replace("'\\''", "'")
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    return value.replace("\\ ", " ")


def parse_alias_line(line: str) -> Dict[str, str]:
    """Parse a single line; returns ``{name: expansion}`` (possibly empty)."""
    stripped = line.strip()
    found: Dict[str, str] = {}
    if stripped.startswith("#"):
        return found
    tokens = split_tokens(stripped)
    if not tokens:
        return found
    if tokens[0] == "alias":
        rest = tokens[1:]
        # Skip bash/zsh flags such as `alias -g` / `alias -s`.
        while rest and rest[0].startswith("-"):
            rest = rest[1:]
        if not rest:
            return found
        if "=" in rest[0]:
            # bash/zsh style, possibly several per line: alias a='x' b='y'
            for token in rest:
                match = _ASSIGN_RE.match(token)
                if match:
                    found[match.group(1)] = normalize(_unquote(match.group(2)))
        elif len(rest) >= 2:
            # fish style: alias name 'expansion'
            found[rest[0]] = normalize(" ".join(_unquote(t) for t in rest[1:]))
    elif tokens[0] == "abbr":
        rest = tokens[1:]
        while rest and rest[0] in _ABBR_BARE_FLAGS:
            rest = rest[1:]
        if len(rest) >= 2 and not rest[0].startswith("-"):
            found[rest[0]] = normalize(" ".join(_unquote(t) for t in rest[1:]))
    return found


def parse_aliases(text: str) -> Dict[str, str]:
    """Parse a whole rc file / ``alias`` dump into ``{name: expansion}``."""
    aliases: Dict[str, str] = {}
    for line in text.splitlines():
        aliases.update(parse_alias_line(line))
    return aliases


def load_alias_files(paths: Sequence[str]) -> Dict[str, str]:
    """Read and merge several alias sources; later files win on conflict."""
    merged: Dict[str, str] = {}
    for path in paths:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            merged.update(parse_aliases(handle.read()))
    return merged


@dataclass(frozen=True)
class IgnoredAlias:
    """An alias the user defined but keeps typing out in full."""

    name: str
    expansion: str
    typed_full: int
    wasted_keystrokes: int


def find_ignored_aliases(
    aliases: Dict[str, str],
    commands: Sequence[str],
    min_count: int = 3,
) -> List[IgnoredAlias]:
    """Find defined aliases whose expansion was still typed in full.

    ``commands`` are normalized history lines. A hit is a command equal to
    the alias expansion or extending it by further arguments. This is the
    guilt-trip section of the report — the data says you own the shortcut
    and refuse to use it.
    """
    ignored: List[IgnoredAlias] = []
    for name in sorted(aliases):
        expansion = aliases[name]
        if not expansion or len(name) >= len(expansion):
            continue
        typed = sum(
            1
            for command in commands
            if command == expansion or command.startswith(expansion + " ")
        )
        if typed >= min_count:
            ignored.append(
                IgnoredAlias(
                    name=name,
                    expansion=expansion,
                    typed_full=typed,
                    wasted_keystrokes=typed * (len(expansion) - len(name)),
                )
            )
    ignored.sort(key=lambda item: (-item.wasted_keystrokes, item.name))
    return ignored
