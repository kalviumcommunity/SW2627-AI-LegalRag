"""Safe, API-facing errors for grounded RAG.

Messages must never contain questions, evidence text, prompts, answers,
credentials, provider payloads, or stack traces.
"""

from __future__ import annotations


class RAGError(Exception):
    """Base class for RAG failures with a safe public message."""

    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RAGQueryError(RAGError):
    """The question, retrieval controls, or evidence request is invalid."""

    status_code = 422


class RAGConfigurationError(RAGError):
    """Database, retrieval, or LLM configuration is unusable."""

    status_code = 503


class RAGGenerationError(RAGError):
    """The LLM response could not be parsed or validated as a grounded answer."""

    status_code = 502


class RAGExecutionError(RAGError):
    """An unexpected non-provider failure occurred while building the answer."""

    status_code = 500
