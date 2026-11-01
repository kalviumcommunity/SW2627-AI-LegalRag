"""Exceptions raised by the property management and intelligence service."""

from __future__ import annotations


class PropertyError(Exception):
    """Base error for all property-service operations."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PropertyNotFoundError(PropertyError):
    """Raised when a requested property cannot be found or is not accessible."""

    def __init__(self, message: str = "Property not found.") -> None:
        super().__init__(message, status_code=404)


class PropertyAuthorizationError(PropertyError):
    """Raised when an operation on a property or document violates tenant ownership."""

    def __init__(
        self, message: str = "Access denied to property or document."
    ) -> None:
        super().__init__(message, status_code=403)


class PropertyValidationError(PropertyError):
    """Raised when input parameters fail semantic validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)
