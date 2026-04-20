from __future__ import annotations

import typing
import logging

import requests

from ..core import app
from . import constants


class VersionManager:
    """Version manager"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    def get_current_version(self) -> str:
        return constants.semantic_version

    async def get_release_list(self) -> list:
        """Fetch release list from Space API (cached GitHub releases)."""
        try:
            rls_list_resp = requests.get(
                url='https://space.langbot.app/api/v1/dist/info/releases',
                proxies=self.ap.proxy_mgr.get_forward_proxies(),
                timeout=10,
            )
            rls_list_resp.raise_for_status()
            resp_json = rls_list_resp.json()
            if resp_json.get('code') == 0 and isinstance(resp_json.get('data'), list):
                return resp_json['data']
            self.ap.logger.warning(f'Failed to fetch release list: unexpected response: {resp_json.get("msg", "")}')
            return []
        except Exception as e:
            self.ap.logger.warning(f'Failed to fetch release list: {e}')
        return []

    async def is_new_version_available(self) -> bool:
        """Check whether a newer version is available."""
        rls_list = await self.get_release_list()
        if not rls_list:
            return False

        current_tag = self.get_current_version()

        latest_tag_name = ''
        for rls in rls_list:
            latest_tag_name = rls.get('tag_name', '')
            break

        return self._is_newer(latest_tag_name, current_tag)

    def _is_newer(self, new_tag: str, old_tag: str) -> bool:
        """Check if new_tag is a newer version than old_tag.

        Compares the first three segments (major.minor.patch) only.
        Returns False if the major version differs (breaking change boundary).
        """
        if not new_tag or not old_tag or new_tag == old_tag:
            return False

        new_parts = new_tag.split('.')
        old_parts = old_tag.split('.')

        # Different major version — not considered an upgrade
        if new_parts[0] != old_parts[0]:
            return False

        if len(new_parts) < 4:
            return True

        return '.'.join(new_parts[:3]) != '.'.join(old_parts[:3])

    async def show_version_update(self) -> typing.Tuple[str, int]:
        try:
            if await self.is_new_version_available():
                return (
                    'New version available. Update guide: https://link.langbot.app/en/docs/update',
                    logging.INFO,
                )
        except Exception as e:
            return f'Error checking version update: {e}', logging.WARNING
