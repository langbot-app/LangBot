from __future__ import annotations

from ..core import app


class ProxyManager:
    ap: app.Application

    forward_proxies: dict[str, str]

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.forward_proxies = {}

    async def initialize(self):
        config = self.ap.cfg_mgr.data

        return (
            {
                "http": config["openai_config"]["proxy"],
                "https": config["openai_config"]["proxy"],
            }
            if "proxy" in config["openai_config"]
            and (config["openai_config"]["proxy"] is not None)
            else None
        )

    def get_forward_proxies(self) -> str:
        return self.forward_proxies
