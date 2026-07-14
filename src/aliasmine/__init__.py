"""aliasmine — mine your shell history for the aliases you should have.

Public API: parse history (:func:`load_history`), run the pipeline
(:func:`analyze`), and render or export the results. The CLI in
:mod:`aliasmine.cli` is a thin shell over exactly these functions.
"""

from .errors import AliasmineError, HistoryNotFoundError
from .existing import IgnoredAlias, find_ignored_aliases, parse_aliases
from .history import HistoryEntry, load_history, parse_history, sniff_format
from .mining import Candidate, corpus_stats, mine, normalized_commands
from .naming import build_reserved, suggest_name
from .pipeline import Analysis, analyze
from .report import render_export, render_scan, render_suggest
from .savings import Suggestion, format_duration, seconds_saved

__version__ = "0.1.0"

__all__ = [
    "AliasmineError",
    "Analysis",
    "Candidate",
    "HistoryEntry",
    "HistoryNotFoundError",
    "IgnoredAlias",
    "Suggestion",
    "__version__",
    "analyze",
    "build_reserved",
    "corpus_stats",
    "find_ignored_aliases",
    "format_duration",
    "load_history",
    "mine",
    "normalized_commands",
    "parse_aliases",
    "parse_history",
    "render_export",
    "render_scan",
    "render_suggest",
    "seconds_saved",
    "sniff_format",
    "suggest_name",
]
