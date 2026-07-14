"""Fish history parsing: the YAML-flavoured `- cmd:` / `when:` format."""

from aliasmine.history import parse_fish


def test_cmd_and_when_pair_up_and_when_is_optional():
    text = "- cmd: git status\n  when: 1626161616\n- cmd: ls -la\n"
    entries = parse_fish(text)
    assert entries[0].command == "git status"
    assert entries[0].timestamp == 1626161616
    assert entries[1].timestamp is None


def test_paths_blocks_are_ignored():
    text = (
        "- cmd: vi notes.md\n"
        "  when: 100\n"
        "  paths:\n"
        "    - notes.md\n"
        "- cmd: git push\n"
        "  when: 200\n"
    )
    entries = parse_fish(text)
    assert [e.command for e in entries] == ["vi notes.md", "git push"]
    assert entries[1].timestamp == 200


def test_fish_escapes_are_undone():
    # fish stores newlines as `\n` and backslashes doubled.
    entries = parse_fish("- cmd: echo 'a\\nb'\n- cmd: grep foo\\\\bar file\n")
    assert entries[0].command == "echo 'a\nb'"
    assert entries[1].command == "grep foo\\bar file"


def test_malformed_entries_are_tolerated():
    # A duplicate `when:` keeps the first value; an empty cmd is dropped.
    text = "- cmd: ls\n  when: 100\n  when: 200\n- cmd: \n  when: 300\n"
    entries = parse_fish(text)
    assert len(entries) == 1
    assert entries[0].timestamp == 100
