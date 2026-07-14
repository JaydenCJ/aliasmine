"""Report rendering and shell-config export: strings users copy-paste."""

import pytest

from aliasmine.history import HistoryEntry
from aliasmine.pipeline import analyze
from aliasmine.report import Style, render_export, render_scan, render_suggest, scan_to_dict
from aliasmine.savings import Suggestion


def _analysis(commands, **kwargs):
    return analyze([HistoryEntry(c) for c in commands], **kwargs)


def test_export_bash_is_deterministic_dateless_alias_lines():
    s = [Suggestion("gs", "git status", 12, "exact")]
    out = render_export(s, "bash")
    assert "alias gs='git status'" in out
    assert out.startswith("# aliasmine: 1 alias,")  # singular — never "1 aliases"
    assert out == render_export(s, "bash")  # no timestamps, clean dotfile diffs


def test_export_escapes_embedded_single_quotes_per_dialect():
    s = Suggestion("gcm", "git commit -m 'wip'", 8, "exact")
    assert "alias gcm='git commit -m '\\''wip'\\'''" in render_export([s], "zsh")
    assert "abbr -a gcm 'git commit -m \\'wip\\''" in render_export([s], "fish")


def test_export_rejects_unknown_format():
    with pytest.raises(ValueError):
        render_export([], "powershell")


def test_scan_report_contains_headline_and_counts(repeated):
    analysis = _analysis(repeated(("git status", 12)))
    text = render_scan(analysis, [("/tmp/h", "bash", 12)])
    assert "You typed `git status` 12 times" in text
    assert "120 keystrokes" in text
    assert "Alias `gs` would have saved" in text


def test_scan_report_marks_prefix_stems(repeated):
    analysis = _analysis(
        repeated(('git commit -m "a"', 3), ('git commit -m "b"', 3))
    )
    text = render_scan(analysis, [("/tmp/h", "bash", 6)])
    assert "git commit -m +" in text
    assert "arguments after it vary" in text


def test_scan_report_flags_ignored_aliases(repeated):
    analysis = _analysis(
        repeated(("git status", 8)), aliases={"gs": "git status"}
    )
    text = render_scan(analysis, [("/tmp/h", "bash", 8)])
    assert "You own alias `gs`" in text
    assert "typed it in full 8 times" in text


def test_scan_report_empty_history_is_helpful():
    analysis = _analysis([])
    text = render_scan(analysis, [("/tmp/h", "bash", 0)])
    assert "--min-count 2" in text


def test_suggest_report_lists_alias_and_totals(repeated):
    analysis = _analysis(repeated(("docker compose up -d", 6)))
    text = render_suggest(analysis)
    assert "dcud" in text
    assert "docker compose up -d" in text
    assert "aliasmine export --format zsh" in text


def test_style_toggle_controls_ansi_codes(repeated):
    analysis = _analysis(repeated(("git status", 12)))
    plain = render_scan(analysis, [("/tmp/h", "bash", 12)], style=Style(False))
    colored = render_scan(analysis, [("/tmp/h", "bash", 12)], style=Style(True))
    assert "\x1b[" not in plain
    assert "\x1b[1m" in colored and colored.count("\x1b[0m") >= 2


def test_scan_to_dict_shape(repeated):
    analysis = _analysis(repeated(("git status", 12)))
    payload = scan_to_dict(analysis, [("/tmp/h", "bash", 12)])
    assert payload["entries"] == 12
    assert payload["top"][0] == {
        "command": "git status",
        "count": 12,
        "kind": "exact",
        "keystrokes": 120,
    }
