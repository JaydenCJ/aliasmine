"""Normalize raw history lines into comparable command strings.

Two people never type the same command the same way twice — extra spaces,
a tab from a paste, a trailing blank. Normalization collapses those so
``git  status`` and ``git status`` mine as one habit, while preserving the
exact text of every token (quotes included) so a proposed alias expands to
something the user actually typed.
"""

from __future__ import annotations

import re
from typing import List, Tuple

#: Matches a leading environment assignment token such as ``FOO=bar``.
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

#: Command prefixes that wrap another command rather than being one.
_WRAPPERS = frozenset({"sudo", "command", "builtin", "nohup", "time", "exec", "doas"})


def split_tokens(command: str) -> List[str]:
    """Split a command on unquoted whitespace, keeping tokens verbatim.

    Unlike :func:`shlex.split` this keeps quotes and escapes inside the
    token text (an alias must expand to what was typed, not a re-quoted
    variant) and never raises on unterminated quotes — history files are
    full of half-typed lines and we must not choke on them.
    """
    tokens: List[str] = []
    current: List[str] = []
    quote = ""
    escaped = False
    for ch in command:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\" and quote != "'":
            current.append(ch)
            escaped = True
            continue
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
            current.append(ch)
            continue
        if ch in " \t\n\r":
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def normalize(command: str) -> str:
    """Collapse a raw history line to its canonical single-line form."""
    return " ".join(split_tokens(command))


def strip_env_prefix(tokens: List[str]) -> Tuple[List[str], List[str]]:
    """Split leading ``NAME=value`` assignments from the command proper.

    Returns ``(assignments, rest)``. ``RUST_LOG=debug cargo test`` groups
    with plain ``cargo test`` for the "commands you run" statistics, though
    mining still treats the full line as what was typed.
    """
    idx = 0
    while idx < len(tokens) and _ENV_ASSIGN_RE.match(tokens[idx]):
        idx += 1
    return tokens[:idx], tokens[idx:]


def head_command(tokens: List[str]) -> str:
    """Return the program a command line actually runs.

    Skips environment assignments and transparent wrappers (``sudo``,
    ``time``, ...) so ``sudo systemctl restart`` counts as ``systemctl``.
    Returns an empty string when there is nothing left.
    """
    _, rest = strip_env_prefix(tokens)
    while rest and rest[0] in _WRAPPERS:
        rest = rest[1:]
        _, rest = strip_env_prefix(rest)
    if not rest:
        return ""
    head = rest[0]
    # `/usr/local/bin/terraform` and `./gradlew` both mine as their basename.
    if "/" in head:
        head = head.rsplit("/", 1)[-1]
    return head


def is_minable(command: str) -> bool:
    """Filter out lines that should never become alias suggestions.

    Comments, shell punctuation, and history-expansion lines (``!!``,
    ``!123``) are keystrokes but not aliasable commands.
    """
    stripped = command.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return False
    if stripped.startswith("!"):
        return False
    first = split_tokens(stripped)
    if not first:
        return False
    head = first[0]
    # A line whose first token is pure punctuation (e.g. `{`, `}` from a
    # pasted script) is noise.
    return any(ch.isalnum() for ch in head)
