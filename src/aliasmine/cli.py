"""The ``aliasmine`` command-line interface.

Subcommands:

* ``scan``    — the shareable report: what you retype and what it costs.
* ``suggest`` — proposed aliases with per-use and total savings.
* ``export``  — emit ready-to-source ``alias`` / ``abbr`` definitions.
* ``stats``   — corpus statistics (entries, unique commands, top programs).

All subcommands read the same inputs (history files, optional alias files)
and share the same mining knobs, so numbers agree across them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional, Sequence, Tuple

from . import __version__
from .errors import AliasmineError
from .existing import load_alias_files
from .history import KNOWN_SHELLS, HistoryEntry, load_history
from .mining import (
    DEFAULT_DOMINANCE,
    DEFAULT_MIN_COUNT,
    DEFAULT_MIN_LENGTH,
    corpus_stats,
)
from .pipeline import Analysis, analyze
from .report import (
    Style,
    render_export,
    render_scan,
    render_suggest,
    scan_to_dict,
    suggest_to_dict,
)
from .savings import DEFAULT_WPM, format_int, pluralize


def _positive_int(value: str) -> int:
    """argparse type for options that must be a positive integer."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "files",
        nargs="*",
        metavar="HISTORY_FILE",
        help="history file(s) to mine; defaults to $HISTFILE and well-known locations",
    )
    parser.add_argument(
        "--shell",
        choices=KNOWN_SHELLS,
        default="auto",
        help="history format (default: auto-detect per file)",
    )
    parser.add_argument(
        "--existing",
        action="append",
        default=[],
        metavar="FILE",
        help="rc file or `alias` output with aliases you already have (repeatable)",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=DEFAULT_MIN_COUNT,
        metavar="N",
        help=f"only mine commands typed at least N times (default: {DEFAULT_MIN_COUNT})",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=DEFAULT_MIN_LENGTH,
        metavar="N",
        help=f"only mine commands at least N characters long (default: {DEFAULT_MIN_LENGTH})",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=20,
        metavar="N",
        dest="max_suggestions",
        help="propose at most N aliases (default: 20)",
    )
    parser.add_argument(
        "--wpm",
        type=_positive_int,
        default=DEFAULT_WPM,
        metavar="N",
        help=f"your typing speed, for time estimates (default: {DEFAULT_WPM})",
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="colorize output (default: auto — TTY only, honors NO_COLOR)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aliasmine",
        description="Mine your shell history for repeated long commands and "
        "propose aliases with quantified keystroke savings.",
    )
    parser.add_argument(
        "--version", action="version", version=f"aliasmine {__version__}"
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    scan = sub.add_parser("scan", help="report your most-retyped long commands")
    _add_common_options(scan)
    scan.add_argument("--top", type=int, default=15, metavar="N", help="rows to show (default: 15)")
    scan.add_argument("--json", action="store_true", help="machine-readable output")

    suggest = sub.add_parser("suggest", help="propose aliases with savings")
    _add_common_options(suggest)
    suggest.add_argument("--json", action="store_true", help="machine-readable output")

    export = sub.add_parser("export", help="emit alias/abbr definitions to source")
    _add_common_options(export)
    export.add_argument(
        "--format",
        choices=("bash", "zsh", "fish"),
        default="bash",
        dest="fmt",
        help="output dialect (default: bash; fish emits abbr definitions)",
    )
    export.add_argument("--out", metavar="FILE", help="write to FILE instead of stdout")

    stats = sub.add_parser("stats", help="corpus statistics for the mined history")
    _add_common_options(stats)
    stats.add_argument("--json", action="store_true", help="machine-readable output")

    return parser


def _want_color(choice: str, stream) -> bool:
    if choice == "always":
        return True
    if choice == "never" or os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _load(args: argparse.Namespace) -> Tuple[List[HistoryEntry], List[Tuple[str, str, int]]]:
    return load_history(args.files, shell=args.shell)


def _analyze(args: argparse.Namespace, entries: Sequence[HistoryEntry]) -> Analysis:
    aliases = load_alias_files(args.existing) if args.existing else {}
    return analyze(
        entries,
        aliases=aliases,
        min_count=args.min_count,
        min_length=args.min_length,
        dominance=DEFAULT_DOMINANCE,
        max_suggestions=args.max_suggestions,
    )


def _cmd_scan(args: argparse.Namespace, out) -> int:
    entries, files = _load(args)
    analysis = _analyze(args, entries)
    if args.json:
        json.dump(scan_to_dict(analysis, files, top=args.top), out, indent=2, sort_keys=True)
        out.write("\n")
        return 0
    style = Style(_want_color(args.color, out))
    out.write(render_scan(analysis, files, top=args.top, wpm=args.wpm, style=style))
    return 0


def _cmd_suggest(args: argparse.Namespace, out) -> int:
    entries, _ = _load(args)
    analysis = _analyze(args, entries)
    if args.json:
        json.dump(suggest_to_dict(analysis, wpm=args.wpm), out, indent=2, sort_keys=True)
        out.write("\n")
        return 0
    style = Style(_want_color(args.color, out))
    out.write(render_suggest(analysis, wpm=args.wpm, style=style))
    return 0


def _cmd_export(args: argparse.Namespace, out) -> int:
    entries, _ = _load(args)
    analysis = _analyze(args, entries)
    text = render_export(analysis.suggestions, args.fmt)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
        out.write(
            f"wrote {pluralize(len(analysis.suggestions), 'alias')} to {args.out} "
            f"({format_int(analysis.total_saved)} keystrokes saved)\n"
        )
    else:
        out.write(text)
    return 0


def _cmd_stats(args: argparse.Namespace, out) -> int:
    entries, files = _load(args)
    stats = corpus_stats(entries)
    if args.json:
        payload = {
            "files": [
                {"path": path, "format": fmt, "entries": count}
                for path, fmt, count in files
            ],
            "entries": stats.total_entries,
            "minable_commands": stats.minable_commands,
            "unique_commands": stats.unique_commands,
            "total_keystrokes": stats.total_keystrokes,
            "avg_command_length": round(stats.avg_length, 1),
            "top_programs": [
                {"program": name, "count": count} for name, count in stats.top_programs
            ],
        }
        json.dump(payload, out, indent=2, sort_keys=True)
        out.write("\n")
        return 0
    lines = [
        f"entries            {format_int(stats.total_entries):>10}",
        f"minable commands   {format_int(stats.minable_commands):>10}",
        f"unique commands    {format_int(stats.unique_commands):>10}",
        f"total keystrokes   {format_int(stats.total_keystrokes):>10}",
        f"avg length         {stats.avg_length:>10.1f}",
        "",
        "top programs:",
    ]
    for name, count in stats.top_programs:
        lines.append(f"  {count:>6,}  {name}")
    out.write("\n".join(lines) + "\n")
    return 0


_HANDLERS = {
    "scan": _cmd_scan,
    "suggest": _cmd_suggest,
    "export": _cmd_export,
    "stats": _cmd_stats,
}


def main(argv: Optional[Sequence[str]] = None, out=None) -> int:
    """CLI entry point; returns the process exit code."""
    out = out if out is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(out)
        return 2
    handler = _HANDLERS[args.command]
    try:
        return handler(args, out)
    except AliasmineError as exc:
        print(f"aliasmine: error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"aliasmine: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
