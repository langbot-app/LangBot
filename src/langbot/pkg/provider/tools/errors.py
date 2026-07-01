class ToolNotFoundError(ValueError):
    """Raised when a requested tool cannot be found in any active loader."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f'Tool not found: {name}')
