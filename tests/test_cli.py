"""End-to-end CLI behavior through main(), with no subprocesses."""

import io
import json

import pytest

from aliasmine import __version__
from aliasmine.cli import main


def _run(argv):
    out = io.StringIO()
    code = main(argv, out=out)
    return code, out.getvalue()


@pytest.fixture
def history(write_file, repeated):
    commands = repeated(
        ("git status", 12),
        ('git commit -m "wip"', 6),
        ("docker compose up -d", 6),
        ("ls", 3),
    )
    return write_file("bash_history", "\n".join(commands) + "\n")


def test_scan_prints_the_shareable_headline(history):
    code, out = _run(["scan", history])
    assert code == 0
    # Ranked by savings potential: the docker habit outranks git status.
    assert "You typed `docker compose up -d` 6 times" in out
    assert "Alias `dcud` would have saved" in out


def test_scan_json_is_valid_and_complete(history):
    code, out = _run(["scan", history, "--json"])
    assert code == 0
    payload = json.loads(out)
    assert payload["entries"] == 27
    assert payload["files"][0]["format"] == "bash"
    assert any(row["command"] == "git status" for row in payload["top"])


def test_suggest_lists_names_and_totals(history):
    code, out = _run(["suggest", history])
    assert code == 0
    assert "gs" in out and "dcud" in out
    assert "keystrokes saved" in out


def test_suggest_json_prices_every_suggestion(history):
    code, out = _run(["suggest", history, "--json"])
    payload = json.loads(out)
    by_alias = {s["alias"]: s for s in payload["suggestions"]}
    assert by_alias["gs"]["total_saved"] == 12 * 8
    assert payload["total_saved"] == sum(
        s["total_saved"] for s in payload["suggestions"]
    )


def test_export_writes_file_or_stdout_per_dialect(history, tmp_path):
    target = tmp_path / "aliases.sh"
    code, out = _run(["export", history, "--format", "zsh", "--out", str(target)])
    assert code == 0
    assert "alias gs='git status'" in target.read_text()
    assert "wrote" in out
    code, out = _run(["export", history, "--format", "fish"])
    assert code == 0
    assert "abbr -a gs 'git status'" in out


def test_stats_json_reports_corpus_numbers(history):
    code, out = _run(["stats", history, "--json"])
    payload = json.loads(out)
    assert payload["entries"] == 27
    assert payload["top_programs"][0]["program"] == "git"


def test_existing_aliases_change_the_output(history, write_file):
    rc = write_file("zshrc", "alias gs='git status'\n")
    code, out = _run(["suggest", history, "--existing", rc])
    assert code == 0
    assert "git status" not in out  # covered; not re-suggested


def test_min_count_threshold_is_respected(history):
    _, strict = _run(["suggest", history, "--min-count", "10", "--json"])
    aliases = [s["alias"] for s in json.loads(strict)["suggestions"]]
    assert aliases == ["gs"]  # only the 12x habit clears 10


def test_missing_history_file_fails_cleanly(tmp_path, capsys):
    code, _ = _run(["scan", str(tmp_path / "absent")])
    assert code == 1
    assert "history file not found" in capsys.readouterr().err


def test_nonpositive_wpm_is_rejected_at_the_parser(history, capsys):
    # A zero WPM would divide by zero deep in the savings model; argparse
    # rejects it up front with a usage error instead of a traceback.
    with pytest.raises(SystemExit) as exc:
        main(["scan", history, "--wpm", "0"])
    assert exc.value.code == 2
    assert "positive integer" in capsys.readouterr().err


def test_no_subcommand_prints_help_and_exits_2():
    code, out = _run([])
    assert code == 2
    assert "scan" in out and "suggest" in out


def test_version_flag_matches_package(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"aliasmine {__version__}"


def test_color_flag_controls_ansi(history):
    _, plain = _run(["scan", history, "--color", "never"])
    _, colored = _run(["scan", history, "--color", "always"])
    assert "\x1b[" not in plain
    assert "\x1b[" in colored
