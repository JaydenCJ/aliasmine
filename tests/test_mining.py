"""Frequency and prefix mining: the analytical heart of aliasmine."""

from aliasmine.history import HistoryEntry
from aliasmine.mining import corpus_stats, mine, normalized_commands, repeat_keystrokes


def _commands(candidates):
    return [c.command for c in candidates]


def test_exact_repetition_is_found(repeated):
    cands = mine(repeated(("git status", 5)), min_count=5, min_length=6)
    assert _commands(cands) == ["git status"]
    assert cands[0].count == 5
    assert cands[0].kind == "exact"


def test_thresholds_exclude_rare_and_short_commands(repeated):
    # 4 < min_count: not a habit. `ls -a` < min_length: nothing to save.
    assert mine(repeated(("git status", 4)), min_count=5, min_length=6) == []
    assert mine(repeated(("ls -a", 50)), min_count=5, min_length=6) == []


def test_prefix_with_varying_tails_is_mined(repeated):
    commands = repeated(
        ('git commit -m "a"', 3),
        ('git commit -m "b"', 2),
        ('git commit -m "c"', 2),
    )
    cands = mine(commands, min_count=5, min_length=6)
    assert "git commit -m" in _commands(cands)
    found = next(c for c in cands if c.command == "git commit -m")
    assert found.count == 7
    assert found.kind == "prefix"


def test_dominant_child_absorbs_its_stem(repeated):
    # Every `docker compose` was `docker compose up -d`: only the long
    # form should be proposed, not the useless stem.
    cands = mine(repeated(("docker compose up -d", 6)), min_count=5, min_length=6)
    assert _commands(cands) == ["docker compose up -d"]


def test_diverse_children_keep_the_stem(repeated):
    # `kubectl get` splits evenly between two resources: the stem is the
    # real habit and both children are below the dominance threshold.
    commands = repeated(("kubectl get pods", 5), ("kubectl get services", 5))
    cands = mine(commands, min_count=5, min_length=6, dominance=0.9)
    assert "kubectl get" in _commands(cands)


def test_exact_count_tracks_full_command_occurrences(repeated):
    commands = repeated(("git push", 6), ("git push origin main", 4))
    cands = mine(commands, min_count=5, min_length=6)
    push = next(c for c in cands if c.command == "git push")
    assert push.count == 10  # 6 exact + 4 as a prefix
    assert push.exact_count == 6
    assert push.kind == "prefix"


def test_ordering_is_by_savings_potential_with_alphabetical_ties(repeated):
    commands = repeated(
        ("git status", 12),  # potential 12 * (10-2) = 96
        ("docker compose up -d", 6),  # potential 6 * (20-2) = 108
    )
    cands = mine(commands, min_count=5, min_length=6)
    assert _commands(cands)[:2] == ["docker compose up -d", "git status"]
    # Equal potential and count: fall back to command text for stability.
    tied = mine(repeated(("cccc dddd", 5), ("aaaa bbbb", 5)), min_count=5, min_length=6)
    assert _commands(tied) == ["aaaa bbbb", "cccc dddd"]


def test_repeat_keystrokes_never_exceeds_the_corpus_total(repeated):
    # `kubectl get` (stem) overlaps both children; naive summing would
    # count those occurrences twice and the "keystrokes on repeats"
    # headline would exceed the keystrokes ever typed. Each occurrence is
    # charged once, to the most specific candidate that covers it.
    commands = repeated(("kubectl get pods", 5), ("kubectl get services", 5))
    cands = mine(commands, min_count=5, min_length=6, dominance=0.9)
    assert "kubectl get" in _commands(cands)  # the stem does survive
    total_typed = sum(len(c) for c in commands)
    assert repeat_keystrokes(cands) == 5 * len("kubectl get pods") + 5 * len(
        "kubectl get services"
    )
    assert repeat_keystrokes(cands) <= total_typed


def test_normalized_commands_drops_noise_and_collapses_whitespace():
    entries = [
        HistoryEntry("git   status"),
        HistoryEntry("# just a note"),
        HistoryEntry("!!"),
        HistoryEntry("   "),
    ]
    assert normalized_commands(entries) == ["git status"]


def test_corpus_stats_counts_programs_through_wrappers():
    entries = [
        HistoryEntry("sudo systemctl restart nginx"),
        HistoryEntry("systemctl status nginx"),
        HistoryEntry("git status"),
    ]
    stats = corpus_stats(entries)
    assert stats.total_entries == 3
    assert stats.unique_commands == 3
    assert dict(stats.top_programs)["systemctl"] == 2


def test_corpus_stats_on_empty_history_is_all_zeros():
    stats = corpus_stats([])
    assert stats.total_entries == 0
    assert stats.avg_length == 0.0
    assert stats.top_programs == ()
