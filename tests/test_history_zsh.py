"""Zsh history parsing: EXTENDED_HISTORY, multi-line commands, fallbacks."""

from aliasmine.history import parse_zsh


def test_extended_entries_parse_timestamp_duration_and_order():
    entries = parse_zsh(": 1626161616:2;git status\n: 1626161700:47;echo a; echo b\n")
    assert [e.command for e in entries] == ["git status", "echo a; echo b"]
    assert entries[0].timestamp == 1626161616
    assert entries[0].duration == 2
    # The `;` after the duration is the delimiter; later ones are command text.
    assert entries[1].duration == 47


def test_multiline_command_is_stitched_with_newlines():
    # zsh writes continued lines with a trailing backslash.
    text = ": 1:0;for f in *.txt; do \\\n  echo $f; \\\ndone\n"
    entries = parse_zsh(text)
    assert len(entries) == 1
    assert entries[0].command == "for f in *.txt; do \n  echo $f; \ndone"


def test_plain_and_mixed_lines_survive_without_extended_headers():
    # A zsh without EXTENDED_HISTORY writes plain lines, and real files
    # mix formats after the option was toggled mid-life.
    entries = parse_zsh("git status\n: 9:0;git push\nls -la\n")
    assert [e.command for e in entries] == ["git status", "git push", "ls -la"]
    assert entries[0].timestamp is None
    assert entries[1].timestamp == 9


def test_entry_with_empty_command_body_is_dropped():
    assert parse_zsh(": 1:0;\n") == []
