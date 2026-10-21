"""Safe, API-facing errors for retrieval.

Messages are intended for API clients and must never contain query text, chunk
text, stack traces, database credentials, or provider payloads.
"""

from __future__ import annotations


class RetrievalError(Exception):
    """Base class for retrieval failures with a safe public message."""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RetrievalQueryError(RetrievalError):
    """The query is empty, too long, or otherwise invalid."""

    status_code = 422


class RetrievalConfigurationError(RetrievalError):
    """Persistence, schema, or embedding configuration is unusable."""

    status_code = 503


class RetrievalDatabaseError(RetrievalError):
    """The database is unavailable or the search query failed."""

    status_code = 503


class RetrievalExecutionError(RetrievalError):
    """A non-transient database failure occurred during search."""

    status_code = 500
