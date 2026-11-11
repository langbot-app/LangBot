from __future__ import annotations


class BoxError(RuntimeError):
    """Base error for LangBot Box failures."""


class BoxValidationError(BoxError):
    """Raised when exec tool arguments are invalid."""


class BoxBackendUnavailableError(BoxError):
    """Raised when no supported container backend is available."""


class BoxRuntimeUnavailableError(BoxError):
    """Raised when the standalone Box Runtime service is unavailable."""


class BoxAdmissionError(BoxError):
    """Raised when a managed sandbox request has no valid admission grant."""


class BoxReadinessError(BoxError):
    """Raised when strict sandbox isolation is not ready."""


class BoxCapacityExceededError(BoxError):
    """Raised when a configured runtime capacity limit is reached."""


class BoxSessionConflictError(BoxError):
    """Raised when an existing session cannot satisfy a new request."""


class BoxSessionNotFoundError(BoxError):
    """Raised when a referenced session does not exist."""


class BoxManagedProcessConflictError(BoxError):
    """Raised when a session already has an active managed process."""


class BoxManagedProcessNotFoundError(BoxError):
    """Raised when a referenced managed process does not exist."""
