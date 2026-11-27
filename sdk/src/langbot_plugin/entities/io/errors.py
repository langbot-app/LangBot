from __future__ import annotations


class ConnectionClosedError(Exception):
    """The connection is closed."""

    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


class ActionCallTimeoutError(Exception):
    """The action call timed out."""

    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


class DependencyInstallError(Exception):
    """One or more plugin dependencies failed to install via pip.

    Carries enough structure for callers to log per-package diagnostics or
    surface them to the UI, instead of a single flattened string.
    """

    def __init__(
        self,
        failed: list[str],
        plugin: str | None = None,
        details: dict[str, str] | None = None,
    ):
        # List of requirement specs that pip could not install (after retries).
        self.failed = failed
        # "<author>/<name>" of the plugin being installed, when known.
        self.plugin = plugin
        # Optional per-package error text (requirement spec -> pip stderr tail).
        self.details = details or {}
        prefix = f"Plugin {plugin} " if plugin else ""
        super().__init__(
            f"{prefix}failed to install {len(failed)} dependencies: {failed}"
        )

    def __str__(self):
        prefix = f"Plugin {self.plugin} " if self.plugin else ""
        return (
            f"{prefix}failed to install {len(self.failed)} dependencies: {self.failed}"
        )


class DependencyVerificationError(Exception):
    """Dependencies were installed but could not be verified afterwards.

    ``missing`` holds requirement specs whose distribution/import could not be
    resolved after pip reported success; ``version_mismatch`` holds specs whose
    installed version does not satisfy the requested specifier.
    """

    def __init__(
        self,
        missing: list[str],
        version_mismatch: list[str] | None = None,
        plugin: str | None = None,
    ):
        self.missing = missing
        self.version_mismatch = version_mismatch or []
        self.plugin = plugin
        prefix = f"Plugin {plugin}: " if plugin else ""
        super().__init__(
            f"{prefix}missing dependencies: {missing}, "
            f"version mismatch: {self.version_mismatch}"
        )

    def __str__(self):
        prefix = f"Plugin {self.plugin}: " if self.plugin else ""
        return (
            f"{prefix}missing dependencies: {self.missing}, "
            f"version mismatch: {self.version_mismatch}"
        )


class ActionCallError(Exception):
    """The action call failed."""

    def __init__(self, message: str, data: dict | None = None):
        self.message = message
        self.data = data or {}

    def __str__(self):
        return self.message
