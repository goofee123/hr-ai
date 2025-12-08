"""Custom exception classes for the application."""

from typing import Any, Optional


class HRMCoreException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(HRMCoreException):
    """Resource not found."""

    pass


class ValidationError(HRMCoreException):
    """Validation error."""

    pass


class AuthenticationError(HRMCoreException):
    """Authentication failed."""

    pass


class AuthorizationError(HRMCoreException):
    """User not authorized for this action."""

    pass


class ConflictError(HRMCoreException):
    """Resource conflict (e.g., duplicate)."""

    pass


class BusinessRuleError(HRMCoreException):
    """Business rule violation."""

    pass


class IntegrationError(HRMCoreException):
    """External integration error."""

    pass


class FileUploadError(HRMCoreException):
    """File upload error."""

    pass
