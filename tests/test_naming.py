"""Alias name generation: short, memorable, and never colliding."""

from aliasmine.naming import (
    COMMON_COMMANDS,
    assign_names,
    build_reserved,
    initials,
    suggest_name,
)


def test_initials_take_the_first_letter_of_every_token():
    # The classics fall out naturally: gs, gcm, dcud.
    assert initials(["git", "status"]) == "gs"
    assert initials(["git", "commit", "-m"]) == "gcm"
    assert initials(["docker", "compose", "up", "-d"]) == "dcud"


def test_tokens_without_alphanumerics_contribute_nothing():
    assert initials(["ls", "--", "*.txt"]) == "lt"


def test_suggest_name_prefers_bare_initials():
    assert suggest_name(["git", "status"], reserved=set()) == "gs"


def test_reserved_name_falls_back_to_extended_form():
    # `gs` taken (ghostscript, or an existing alias) -> grow from the
    # last token: gst.
    assert suggest_name(["git", "status"], reserved={"gs"}) == "gst"


def test_single_token_command_walks_its_own_prefixes():
    assert suggest_name(["kubectl"], reserved=set()) == "k"
    assert suggest_name(["kubectl"], reserved={"k"}) == "ku"


def test_name_must_save_at_least_two_characters():
    # A 3-char command can't be beaten by >= 2 chars with a 2-char alias.
    assert suggest_name(["git"], reserved={"g"}) is None


def test_common_commands_are_never_shadowed():
    # `cd` would be the initials of `cargo doc`; it must be skipped.
    assert "cd" in COMMON_COMMANDS
    name = suggest_name(["cargo", "doc"], reserved=set(COMMON_COMMANDS))
    assert name == "cdo"


def test_build_reserved_covers_history_programs_and_existing_aliases():
    reserved = build_reserved(
        ["terraform plan", "terraform apply"], existing_aliases=["gs", "gp"]
    )
    assert "terraform" in reserved
    assert {"gs", "gp"} <= reserved


def test_assign_names_never_hands_out_duplicates_and_is_deterministic():
    pairs = [
        (("git", "status"), "git status"),
        (("git", "stash"), "git stash"),  # initials also `gs`
    ]
    first = assign_names(list(pairs), reserved=set())
    second = assign_names(list(pairs), reserved=set())
    assert first == second
    assert first[0] == "gs"
    assert first[1] is not None and first[1] != "gs"
