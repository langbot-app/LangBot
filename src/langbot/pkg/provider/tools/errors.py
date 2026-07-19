class ToolNotFoundError(ValueError):
    """Raised when a requested tool cannot be found in any active loader."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f'Tool not found: {name}')


class ToolExecutionDeniedError(PermissionError):
    """Raised when a known tool is not allowed in the current execution context."""

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason
        super().__init__(f'Tool execution denied for {name}: {reason}')
