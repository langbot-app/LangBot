from __future__ import annotations

import os
import sys

from ..core import app


class ProxyManager:
    """代理管理器
    """

    ap: app.Application

    forward_proxies: dict[str, str]

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.forward_proxies = {}

    async def initialize(self):
        self.forward_proxies = {
            "http://": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
            "https://": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
        }

        if 'http' in self.ap.system_cfg.data['network-proxies']:
            self.forward_proxies['http://'] = self.ap.system_cfg.data['network-proxies']['http']
        if 'https' in self.ap.system_cfg.data['network-proxies']:
            self.forward_proxies['https://'] = self.ap.system_cfg.data['network-proxies']['https']

    def get_forward_proxies(self) -> dict:
        return self.forward_proxies.copy()
