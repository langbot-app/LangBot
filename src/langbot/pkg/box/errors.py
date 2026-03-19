from __future__ import annotations


class BoxError(RuntimeError):
    """Base error for LangBot Box failures."""


class BoxValidationError(BoxError):
    """Raised when sandbox_exec arguments are invalid."""


class BoxBackendUnavailableError(BoxError):
    """Raised when no supported container backend is available."""


class BoxSessionConflictError(BoxError):
    """Raised when an existing session cannot satisfy a new request."""
