"""The savings arithmetic: keystrokes are exact, time is an honest model."""

import pytest

from aliasmine.savings import (
    Suggestion,
    chars_per_second,
    format_duration,
    format_int,
    pluralize,
    seconds_saved,
    total_savings,
)


def test_savings_are_length_difference_times_count():
    s = Suggestion(name="gs", command="git status", count=340, kind="exact")
    assert s.saved_per_use == 8
    assert s.total_saved == 340 * 8


def test_total_savings_sums_suggestions():
    a = Suggestion("gs", "git status", 10, "exact")  # 8 per use
    b = Suggestion("gp", "git push", 5, "exact")  # 6 per use
    assert total_savings([a, b]) == 10 * 8 + 5 * 6


def test_time_model_is_wpm_based():
    # 60 WPM is 5 chars/second, so 300 chars is exactly a minute.
    assert chars_per_second(60) == pytest.approx(5.0)
    assert seconds_saved(300, wpm=60) == pytest.approx(60.0)


def test_nonpositive_wpm_is_rejected():
    with pytest.raises(ValueError):
        chars_per_second(0)


def test_format_duration_boundaries():
    assert format_duration(48) == "48s"
    assert format_duration(59.6) == "1m"  # rounds up across the boundary
    assert format_duration(12 * 60) == "12m"
    assert format_duration(2 * 3600 + 5 * 60) == "2h 05m"
    assert format_duration(50 * 3600) == "2d 2h"


def test_format_int_thousands_separator():
    assert format_int(48213) == "48,213"
    assert format_int(7) == "7"


def test_pluralize_inflects_and_formats_the_count():
    # Reports must never say "1 aliases" or "1 times".
    assert pluralize(1, "alias") == "1 alias"
    assert pluralize(18, "alias") == "18 aliases"
    assert pluralize(1, "time") == "1 time"
    assert pluralize(48213, "keystroke") == "48,213 keystrokes"
