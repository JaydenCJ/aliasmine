"""The analyze() pipeline: mining, naming, and alias-awareness combined."""

from aliasmine.history import HistoryEntry
from aliasmine.pipeline import analyze


def _entries(commands):
    return [HistoryEntry(c) for c in commands]


def test_pipeline_produces_named_priced_suggestions(repeated):
    analysis = analyze(_entries(repeated(("git status", 12))))
    assert len(analysis.suggestions) == 1
    s = analysis.suggestions[0]
    assert (s.name, s.command, s.count) == ("gs", "git status", 12)
    assert analysis.total_saved == 12 * 8


def test_commands_covered_by_existing_alias_are_not_resuggested(repeated):
    analysis = analyze(
        _entries(repeated(("git status", 12))), aliases={"gs": "git status"}
    )
    assert analysis.suggestions == []
    # ...but the habit still shows up as an ignored alias.
    assert analysis.ignored_aliases[0].name == "gs"


def test_existing_alias_names_are_reserved_for_new_suggestions(repeated):
    analysis = analyze(
        _entries(repeated(("git stash pop", 6))), aliases={"gsp": "grep -rn"}
    )
    names = [s.name for s in analysis.suggestions]
    assert names and "gsp" not in names


def test_max_suggestions_caps_the_list(repeated):
    commands = repeated(
        ("aaaa bbbb cccc", 5), ("dddd eeee ffff", 5), ("gggg hhhh iiii", 5)
    )
    analysis = analyze(_entries(commands), max_suggestions=2)
    assert len(analysis.suggestions) == 2
    # Candidates are unaffected by the cap — the report still shows all.
    assert len(analysis.candidates) == 3


def test_suggestions_follow_candidate_ranking(repeated):
    commands = repeated(("git status", 12), ("docker compose up -d", 6))
    analysis = analyze(_entries(commands))
    assert [s.command for s in analysis.suggestions] == [
        "docker compose up -d",
        "git status",
    ]


def test_overlapping_stem_and_child_are_not_double_charged(repeated):
    # `kubectl get` (stem, 10 uses) plus its two children (5 each): the
    # stem's uses are fully covered by the children, so it prices at zero
    # and is dropped — the grand total never counts a keystroke twice.
    commands = repeated(("kubectl get pods", 5), ("kubectl get services", 5))
    analysis = analyze(_entries(commands))
    by_command = {s.command: s for s in analysis.suggestions}
    assert "kubectl get" not in by_command
    assert set(by_command) == {"kubectl get pods", "kubectl get services"}
    assert analysis.total_saved == sum(s.total_saved for s in analysis.suggestions)


def test_repeat_keystrokes_counts_only_surviving_candidates(repeated):
    analysis = analyze(_entries(repeated(("git status", 12), ("ls", 12))))
    # `ls` is below min_length and contributes nothing.
    assert analysis.repeat_keystrokes == 12 * len("git status")
