from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from quart import Quart

from langbot.pkg.api.http.controller.groups import user as user_module
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.core.stages.genkeys import GenKeysStage
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.utils import constants
from langbot.pkg.workspace.collaboration import WorkspaceCollaborationService
from langbot.pkg.workspace.service import WorkspaceService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_generated_recovery_code_resets_real_sqlite_account(tmp_path, monkeypatch):
    """Exercise generation, reset, and old/new password login without mocked user services."""
    monkeypatch.setattr(constants, 'instance_id', 'recovery-journey')
    monkeypatch.setattr(user_module, '_reset_password_state', {'window_started_at': 0.0, 'attempts': 0})
    monkeypatch.setattr(user_module, 'asyncio', SimpleNamespace(sleep=AsyncMock()))
    application = SimpleNamespace(
        logger=logging.getLogger('recovery-password-journey'),
        instance_config=SimpleNamespace(
            data={
                'database': {'use': 'sqlite', 'sqlite': {'path': str(tmp_path / 'recovery.db')}},
                'system': {
                    'jwt': {'secret': 'recovery-journey-test-secret-only', 'expire': 3600},
                    'recovery_key': '',
                },
            },
            dump_config=AsyncMock(),
        ),
    )
    await GenKeysStage().run(application)
    key = application.instance_config.data['system']['recovery_key']
    assert len(key) == 8
    assert set(key) <= set('23456789ABCDEFGHJKLMNPQRSTUVWXYZ')
    persistence = PersistenceManager(application)
    application.persistence_mgr = persistence
    try:
        await persistence.initialize()
        application.workspace_service = WorkspaceService(application, instance_uuid='recovery-journey')
        application.workspace_collaboration_service = WorkspaceCollaborationService(
            application, application.workspace_service
        )
        application.user_service = UserService(application)
        quart_app = Quart(__name__)
        await UserRouterGroup(application, quart_app).initialize()
        client = quart_app.test_client()

        initial = await client.post(
            '/api/v1/user/init', json={'user': 'owner@example.com', 'password': 'OriginalPass1!'}
        )
        assert initial.status_code == 200
        assert (await initial.get_json())['code'] == 0

        payload = {'user': 'owner@example.com', 'recovery_key': 'WRONG', 'new_password': 'RecoveredPass1!'}
        wrong = await client.post('/api/v1/user/reset-password', json=payload)
        assert wrong.status_code == 403
        unchanged = await client.post(
            '/api/v1/user/auth', json={'user': 'owner@example.com', 'password': 'OriginalPass1!'}
        )
        assert (await unchanged.get_json())['code'] == 0

        reset = await client.post('/api/v1/user/reset-password', json={**payload, 'recovery_key': key})
        assert reset.status_code == 200
        assert (await reset.get_json())['code'] == 0
        old_login = await client.post(
            '/api/v1/user/auth', json={'user': 'owner@example.com', 'password': 'OriginalPass1!'}
        )
        assert (await old_login.get_json())['code'] != 0
        new_login = await client.post(
            '/api/v1/user/auth', json={'user': 'owner@example.com', 'password': 'RecoveredPass1!'}
        )
        new_data = await new_login.get_json()
        assert new_data['code'] == 0
        assert new_data['data']['token']
    finally:
        await persistence.get_db_engine().dispose()
