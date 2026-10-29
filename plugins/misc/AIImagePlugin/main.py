from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin

DEFAULT_BASE_URL = "https://api.qhaigc.net"


class AIImagePlugin(BasePlugin):
    """Process-wide plugin object; the OpenAI client is built per invocation.

    There is deliberately no cached client attribute: a shared worker serves every
    installation of this artifact digest from one object, and ``initialize()`` is
    called once with an empty config, so a client stored here would carry one
    tenant's API key and base URL into every other tenant's invocation.
    """

    def create_client(self):
        """Build an OpenAI-compatible client from this invocation's configuration.

        ``AsyncOpenAI`` is a thin httpx wrapper and is cheap to construct, so it is
        created and closed inside the invocation that needs it.
        """

        config = self.get_config()
        api_key = str(config.get("openai_api_key", "") or "")
        if not api_key:
            return None
        base_url = str(config.get("api_base_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL)

        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=api_key, base_url=base_url)
