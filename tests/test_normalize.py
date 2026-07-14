"""Tokenization and normalization: the foundation every count rests on."""

from aliasmine.normalize import (
    head_command,
    is_minable,
    normalize,
    split_tokens,
    strip_env_prefix,
)


def test_split_on_unquoted_whitespace():
    assert split_tokens("git   status") == ["git", "status"]


def test_quotes_keep_spaces_and_the_quotes_themselves():
    # Tokens stay verbatim so an alias expands to what was typed.
    assert split_tokens('git commit -m "fix the bug"') == [
        "git",
        "commit",
        "-m",
        '"fix the bug"',
    ]
    assert split_tokens("echo 'a b'") == ["echo", "'a b'"]


def test_backslash_escapes_a_space():
    assert split_tokens("cat my\\ file.txt") == ["cat", "my\\ file.txt"]


def test_unterminated_quote_does_not_raise():
    # Half-typed lines are everywhere in real history; shlex would raise.
    assert split_tokens('echo "oops') == ["echo", '"oops']


def test_normalize_collapses_tabs_and_runs_of_spaces():
    assert normalize("git \t  status ") == "git status"


def test_normalize_is_idempotent():
    once = normalize("docker   compose  up   -d")
    assert normalize(once) == once


def test_strip_env_prefix_splits_assignments():
    env, rest = strip_env_prefix(["RUST_LOG=debug", "cargo", "test"])
    assert env == ["RUST_LOG=debug"]
    assert rest == ["cargo", "test"]


def test_head_command_skips_wrappers_env_and_paths():
    assert head_command(["sudo", "PORT=8080", "systemctl", "restart"]) == "systemctl"
    assert head_command(["./gradlew", "build"]) == "gradlew"


def test_is_minable_separates_commands_from_noise():
    assert is_minable("git status")
    assert is_minable("ls")
    assert not is_minable("# a note to self")
    assert not is_minable("!!")
    assert not is_minable("   ")
