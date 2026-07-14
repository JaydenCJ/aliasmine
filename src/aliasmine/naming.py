"""Generate short, collision-free alias names for mined commands.

A proposed alias is worthless if it shadows ``ls`` or the user's existing
``gs``. Every generated name is checked against three reserved sets: a
curated list of common executables, every program actually seen in the
mined history, and every name already assigned (existing aliases plus
earlier suggestions in the same run). Generation is deterministic — the
same history always yields the same names.
"""

from __future__ import annotations

from typing import Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from .normalize import head_command, split_tokens

#: Common executables and shell builtins an alias must never shadow.
#: Curated from POSIX, coreutils, and the usual suspects on a dev box.
COMMON_COMMANDS = frozenset(
    """
    alias awk bash bc bg cal cat cd chgrp chmod chown clear cmp comm cp
    cron crontab csh curl cut dash date dd df diff dig dirs du echo ed env eval
    exec exit expr false fc fg file find fish fmt fold free fzf g gcc gdb git
    go grep groups gzip halt hash head help history host hostname id
    ifconfig install jobs join jq kill killall ksh last ldd less let ln locale
    locate login logout ls lsof make man mkdir mktemp more mount mv nc
    netstat nice nl nm node nohup npm nproc nslookup od op passwd paste
    patch pgrep ping pip pkill popd printf ps pushd pwd python read
    readlink reboot rev rm rmdir rsync ruby scp screen sed seq set sh
    shred shutdown sleep sort source split ssh stat strings strip stty
    su sudo sync tac tail tar tcsh tee test time top touch tr trap true
    tty type ulimit umask umount uname uniq unset unzip uptime users vi
    vim w wait watch wc wget whatis whereis which who whoami xargs yes
    zip zsh
    """.split()
)

#: Hard floor: an alias must beat the command it replaces by this many chars.
MIN_SAVING_PER_USE = 2


def _alnum(text: str) -> str:
    """Lower-cased alphanumeric characters of a token, dashes stripped."""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def initials(tokens: Sequence[str]) -> str:
    """First meaningful character of each token: ``git status`` -> ``gs``.

    Option tokens contribute their first letter too (``-m`` -> ``m``), which
    is how the classic ``gcm`` for ``git commit -m`` falls out naturally.
    Tokens with no alphanumerics (lone ``--``, redirects) contribute nothing.
    """
    letters: List[str] = []
    for token in tokens:
        cleaned = _alnum(token)
        if cleaned:
            letters.append(cleaned[0])
    return "".join(letters)


def _candidate_names(tokens: Sequence[str]) -> Iterator[str]:
    """Yield alias names for ``tokens`` in preference order, best first.

    Multi-token commands start from their initials and grow by borrowing
    more characters from the last contributing token (``gs`` -> ``gst`` ->
    ``gsta`` for ``git status``). Single-token commands walk their own
    prefixes (``k`` -> ``ku`` -> ``kub`` for ``kubectl``). Numbered
    fallbacks guarantee the iterator is never empty.
    """
    words = [_alnum(t) for t in tokens]
    words = [w for w in words if w]
    if not words:
        return
    if len(words) == 1:
        word = words[0]
        for length in range(1, len(word)):
            yield word[:length]
        base = word[0]
    else:
        base = "".join(w[0] for w in words)
        yield base
        tail = words[-1]
        for extra in range(1, len(tail)):
            yield base + tail[1 : 1 + extra]
    for number in range(2, 100):
        yield f"{base}{number}"


def suggest_name(
    tokens: Sequence[str],
    reserved: Set[str],
    command_length: Optional[int] = None,
) -> Optional[str]:
    """Pick the best available alias name, or ``None`` if nothing saves.

    A name is rejected when it is reserved or when it would not save at
    least :data:`MIN_SAVING_PER_USE` characters per use — an alias as long
    as its expansion is clutter, not help.
    """
    if command_length is None:
        command_length = len(" ".join(tokens))
    for name in _candidate_names(tokens):
        if len(name) > command_length - MIN_SAVING_PER_USE:
            # Names only grow from here; give up rather than loop.
            return None
        if name in reserved:
            continue
        return name
    return None


def build_reserved(
    commands: Iterable[str],
    existing_aliases: Iterable[str] = (),
) -> Set[str]:
    """Assemble the full reserved-name set for one suggestion run.

    ``commands`` are the normalized history lines: every program the user
    actually runs is reserved, so a suggestion can never shadow a real
    workflow even if we have never heard of the tool.
    """
    reserved: Set[str] = set(COMMON_COMMANDS)
    reserved.update(existing_aliases)
    for command in commands:
        head = head_command(split_tokens(command))
        if head:
            reserved.add(head.lower())
    return reserved


def assign_names(
    candidates: Sequence[Tuple[Tuple[str, ...], str]],
    reserved: Set[str],
) -> List[Optional[str]]:
    """Assign a unique name to each ``(tokens, command)`` pair, in order.

    Earlier candidates (higher savings) get first pick of the short names.
    The reserved set is mutated as names are taken so no two suggestions
    collide with each other. Returns ``None`` for candidates that cannot
    be named profitably.
    """
    names: List[Optional[str]] = []
    for tokens, command in candidates:
        name = suggest_name(tokens, reserved, command_length=len(command))
        if name is not None:
            reserved.add(name)
        names.append(name)
    return names
