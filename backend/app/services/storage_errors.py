"""Safe, API-facing errors for persistent vector storage."""

from app.services.ingestion_errors import DocumentIngestionError


class DocumentStorageUnavailableError(DocumentIngestionError):
    """The database is not configured, unreachable, or has no usable schema."""

    status_code = 503


class DatabaseConfigurationError(DocumentStorageUnavailableError):
    """Persistence is not configured (for example, DATABASE_URL is missing)."""


class DatabaseUnavailableError(DocumentStorageUnavailableError):
    """A connection to the database could not be established."""


class DatabaseSchemaError(DocumentStorageUnavailableError):
    """The schema or pgvector extension has not been initialized/applied."""


class DatabaseWriteError(DocumentIngestionError):
    """A transaction failed while writing document/chunk records."""

    status_code = 500
