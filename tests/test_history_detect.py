"""Format sniffing, zsh unmetafication, and multi-file loading."""

import pytest

from aliasmine.errors import HistoryNotFoundError
from aliasmine.history import (
    default_history_files,
    load_history,
    read_history_file,
    sniff_format,
)


def test_sniff_by_content_markers_with_bash_fallback():
    assert sniff_format(": 1626161616:0;git status\n") == "zsh"
    assert sniff_format("- cmd: git status\n") == "fish"
    assert sniff_format("git status\nls\n") == "bash"
    assert sniff_format("") == "bash"


def test_sniff_fish_by_filename_wins_over_content():
    # The filename shortcut must hold even for an empty fish_history.
    assert sniff_format("", path="/home/u/.local/share/fish/fish_history") == "fish"


def test_read_history_file_unmetafies_zsh_bytes(tmp_path):
    # zsh stores 0x83, (b ^ 0x20) for bytes >= 0x83; a UTF-8 é (0xC3 0xA9)
    # becomes 0x83 0xE3 0x83 0x89 on disk.
    path = tmp_path / "hist"
    path.write_bytes(b": 1:0;echo caf\x83\xe3\x83\x89\n")
    entries, fmt = read_history_file(str(path))
    assert fmt == "zsh"
    assert entries[0].command == "echo café"


def test_load_history_merges_multiple_files_in_order(write_file):
    bash = write_file("bash_history", "git status\n")
    zsh = write_file("zsh_history", ": 1:0;git push\n")
    entries, files = load_history([bash, zsh])
    assert [e.command for e in entries] == ["git status", "git push"]
    assert [(f[1], f[2]) for f in files] == [("bash", 1), ("zsh", 1)]


def test_load_history_missing_file_raises(tmp_path):
    with pytest.raises(HistoryNotFoundError):
        load_history([str(tmp_path / "nope")])


def test_default_discovery_honors_histfile_env(write_file, monkeypatch):
    hist = write_file("some_history", "ls\n")
    monkeypatch.setenv("HISTFILE", hist)
    assert default_history_files()[0] == hist


def test_forced_shell_overrides_detection(write_file):
    # Force bash on a zsh-looking file: the header is kept as a command.
    path = write_file("h", ": 1:0;git status\n")
    entries, files = load_history([path], shell="bash")
    assert files[0][1] == "bash"
    assert entries[0].command == ": 1:0;git status"
