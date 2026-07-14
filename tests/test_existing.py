"""Parsing the aliases a user already has, in three shells' dialects."""

from aliasmine.existing import find_ignored_aliases, parse_alias_line, parse_aliases


def test_bash_alias_with_single_or_double_quotes():
    assert parse_alias_line("alias gs='git status'") == {"gs": "git status"}
    assert parse_alias_line('alias gl="git log --oneline"') == {"gl": "git log --oneline"}


def test_multiple_assignments_on_one_line():
    parsed = parse_alias_line("alias gs='git status' gp='git push'")
    assert parsed == {"gs": "git status", "gp": "git push"}


def test_fish_alias_and_abbr_forms():
    assert parse_alias_line("alias gs 'git status'") == {"gs": "git status"}
    assert parse_alias_line("abbr -a gs 'git status'") == {"gs": "git status"}
    assert parse_alias_line("abbr --add gco git checkout") == {"gco": "git checkout"}


def test_comments_and_unrelated_lines_are_ignored_and_later_wins():
    text = (
        "# my aliases\n"
        "export PATH=$PATH:/opt/bin\n"
        "alias gs='git status'\n"
        "alias gs='git stash'\n"
    )
    assert parse_aliases(text) == {"gs": "git stash"}


def test_posix_quote_splicing_is_unwrapped():
    # alias say='echo '\''hi'\''' — the classic quoted-quote dance.
    assert parse_alias_line("alias say='echo '\\''hi'\\'''")["say"] == "echo 'hi'"


def test_ignored_alias_found_when_expansion_typed_in_full():
    aliases = {"gs": "git status"}
    commands = ["git status"] * 4 + ["git status -sb"] * 2 + ["ls"]
    ignored = find_ignored_aliases(aliases, commands, min_count=3)
    assert len(ignored) == 1
    assert ignored[0].name == "gs"
    assert ignored[0].typed_full == 6  # exact + extended-by-arguments
    assert ignored[0].wasted_keystrokes == 6 * (len("git status") - len("gs"))


def test_alias_not_flagged_below_threshold():
    ignored = find_ignored_aliases({"gs": "git status"}, ["git status"] * 2, min_count=3)
    assert ignored == []


def test_alias_longer_than_expansion_is_never_flagged():
    # A decorative alias like `gitstatus='git st'` saves nothing; skip it.
    ignored = find_ignored_aliases({"longername": "git st"}, ["git st"] * 10)
    assert ignored == []
