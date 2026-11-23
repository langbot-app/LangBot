"""Dedicated-environment (edition=cloud on OSS persistence) Space provider coverage.

A dedicated environment runs the OSS runtime with ``system.edition = cloud``. The
process-level ``LangBot Models`` compatibility provider is part of the OSS
single-Workspace contract, so gating its creation on ``edition == 'community'``
left dedicated Cores without the row and broke Space OAuth login with
"Provider not found".
"""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def get_persistence_module():
    return import_module('langbot.pkg.persistence.mgr')


def _manager(edition: str, *, multi_workspace_enabled: bool, workspace_uuids: list[str]):
    persistence = get_persistence_module()
    app = Mock()
    app.persistence_mgr = None
    app.instance_config = SimpleNamespace(data={'space': {'models_gateway_api_url': 'https://models.example.test/v1'}})
    app.deployment = SimpleNamespace(multi_workspace_enabled=multi_workspace_enabled)
    app.logger = Mock()

    mgr = persistence.PersistenceManager(app)
    mgr.execute_async = AsyncMock()

    workspace_result = Mock()
    workspace_result.scalars.return_value.all.return_value = workspace_uuids
    provider_result = Mock()
    provider_result.first.return_value = None
    # Third call is the INSERT of the compatibility provider.
    mgr.execute_async.side_effect = [workspace_result, provider_result, Mock()]
    return mgr


class TestWriteSpaceModelProviders:
    @pytest.mark.asyncio
    async def test_dedicated_cloud_edition_creates_compatibility_provider(self, monkeypatch):
        """edition=cloud on a single Workspace must still own the provider row."""
        constants = import_module('langbot.pkg.utils.constants')
        monkeypatch.setattr(constants, 'edition', 'cloud')

        mgr = _manager('cloud', multi_workspace_enabled=False, workspace_uuids=['workspace-a'])
        await mgr.write_space_model_providers()

        # One select for the Workspace list, one for the existing provider, one insert.
        assert mgr.execute_async.await_count == 3

    @pytest.mark.asyncio
    async def test_multi_workspace_cloud_never_projects_provider(self, monkeypatch):
        """Real multi-tenant Cloud keeps the provider out of its Workspaces."""
        constants = import_module('langbot.pkg.utils.constants')
        monkeypatch.setattr(constants, 'edition', 'cloud')

        mgr = _manager('cloud', multi_workspace_enabled=True, workspace_uuids=['workspace-a'])
        await mgr.write_space_model_providers()

        mgr.execute_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_community_edition_still_creates_provider(self, monkeypatch):
        constants = import_module('langbot.pkg.utils.constants')
        monkeypatch.setattr(constants, 'edition', 'community')

        mgr = _manager('community', multi_workspace_enabled=False, workspace_uuids=['workspace-a'])
        await mgr.write_space_model_providers()

        assert mgr.execute_async.await_count == 3
