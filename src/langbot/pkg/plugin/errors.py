"""Shared plugin operation errors without runtime or application imports."""


class PluginRuntimeNotConnectedError(RuntimeError):
    """Raised when plugin runtime operations are requested before connection."""


class PluginInstallationFailedError(RuntimeError):
    """Stable Runtime desired-state failure for one plugin installation."""

    def __init__(
        self,
        installation_uuid: str,
        error_code: str,
        message: str,
    ) -> None:
        self.installation_uuid = installation_uuid
        self.error_code = error_code
        self.runtime_message = message
        super().__init__(f'Plugin installation {installation_uuid} failed [{error_code}]: {message}')


class MarketplacePluginVersionNotFoundError(ValueError):
    """The requested release is not available from the marketplace."""
