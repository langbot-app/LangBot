"""Runner examples activated by explicit LangBot processor instances."""

from langbot_plugin.api.definition.plugin import BasePlugin


class RunnerDemo(BasePlugin):
    async def initialize(self) -> None:
        pass
