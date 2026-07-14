"""Bash history parsing: plain lines and HISTTIMEFORMAT timestamps."""

from aliasmine.history import parse_bash


def test_plain_lines_become_entries_in_order_skipping_blanks():
    entries = parse_bash("git status\n\n   \nls -la\ngit push\n")
    assert [e.command for e in entries] == ["git status", "ls -la", "git push"]


def test_histtimeformat_epoch_attaches_only_to_the_next_command():
    entries = parse_bash("#1626161616\ngit status\nls\n")
    assert entries[0].command == "git status"
    assert entries[0].timestamp == 1626161616
    assert entries[1].timestamp is None


def test_hash_lines_that_are_not_epochs_are_kept_as_commands():
    # `# TODO fix later` was real keystrokes, and `#123` is far too short
    # to be an epoch: neither may be swallowed as metadata.
    entries = parse_bash("# TODO fix later\n#123\ngit status\n")
    assert [e.command for e in entries] == ["# TODO fix later", "#123", "git status"]


def test_source_is_recorded_and_empty_input_yields_nothing():
    assert parse_bash("ls\n", source="/tmp/h")[0].source == "/tmp/h"
    assert parse_bash("") == []
