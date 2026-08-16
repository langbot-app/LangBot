from __future__ import annotations

try:
    from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError
except ModuleNotFoundError:

    class NotSupportedError(Exception):
        def __init__(self, api_name: str, *args):
            super().__init__(f"API '{api_name}' is not supported by this adapter", *args)
            self.api_name = api_name

