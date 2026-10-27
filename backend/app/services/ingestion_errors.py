"""Safe, application-level errors for the document ingestion pipeline.

Messages are intended for API clients: they must never contain stack traces,
filesystem paths, document contents, or other internal details.
"""


class DocumentIngestionError(Exception):
    """Base class for ingestion failures with a safe public message."""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DocumentValidationError(DocumentIngestionError):
    """The upload failed validation (empty, invalid signature, bad encoding)."""

    status_code = 400


class UnsupportedDocumentTypeError(DocumentValidationError):
    """The file extension or declared MIME type is not supported."""

    status_code = 415


class DocumentTooLargeError(DocumentValidationError):
    """The upload exceeds the configured maximum size."""

    status_code = 413


class DocumentExtractionError(DocumentIngestionError):
    """The document could not be read or its text could not be extracted."""

    status_code = 422


class EncryptedDocumentError(DocumentExtractionError):
    """The PDF is password protected and cannot be processed."""


class DocumentStorageError(DocumentIngestionError):
    """Secure temporary storage failed."""

    status_code = 500


class DocumentNotFoundError(DocumentIngestionError):
    """The requested document was not found."""

    status_code = 404


class DocumentIdentifierError(DocumentValidationError):
    """The provided document identifier is invalid."""

    status_code = 422

