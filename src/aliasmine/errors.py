"""Exception types for aliasmine.

Every error the CLI surfaces to a user derives from :class:`AliasmineError`,
so callers embedding the library can catch one type and get all of them.
"""

from __future__ import annotations


class AliasmineError(Exception):
    """Base class for all aliasmine errors."""


class HistoryNotFoundError(AliasmineError):
    """No usable history file was given and none could be discovered."""
