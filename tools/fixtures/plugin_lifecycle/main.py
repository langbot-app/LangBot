from langbot_plugin.api.definition.plugin import BasePlugin

VERSION = '0.0.0'
FAIL_INITIALIZE = False


class LifecyclePlugin(BasePlugin):
    version = VERSION

    async def initialize(self):
        if FAIL_INITIALIZE:
            raise RuntimeError('QA deliberate initialization failure')
