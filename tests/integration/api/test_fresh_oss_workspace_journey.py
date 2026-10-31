from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from quart import Quart

from langbot.pkg.api.http.controller.groups.system import SystemRouterGroup
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.api.http.controller.groups.workspaces import WorkspacesRouterGroup
from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.utils import constants
from langbot.pkg.workspace.collaboration import WorkspaceCollaborationService
from langbot.pkg.workspace.service import WorkspaceService


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _authorization(token: str, workspace_uuid: str | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {token}'}
    if workspace_uuid is not None:
        headers['X-Workspace-Id'] = workspace_uuid
    return headers


async def test_fresh_oss_workspace_http_journey_uses_real_sqlite_persistence(
    tmp_path,
    monkeypatch,
):
    """Exercise the first-run Workspace journey through real HTTP handlers."""

    instance_uuid = 'fresh-oss-workspace-journey'
    monkeypatch.setattr(constants, 'instance_id', instance_uuid)

    application = SimpleNamespace(
        logger=logging.getLogger('fresh-oss-workspace-journey-test'),
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'use': 'sqlite',
                    'sqlite': {'path': str(tmp_path / 'langbot.db')},
                },
                'system': {
                    'jwt': {'secret': 'fresh-oss-workspace-secret', 'expire': 3600},
                    'allow_modify_login_info': True,
                    'limitation': {},
                    'outbound_ips': [],
                },
                'api': {'global_api_key': ''},
                'plugin': {'enable_marketplace': True},
                'space': {
                    'url': 'https://space.langbot.app',
                    'models_gateway_api_url': 'https://api.langbot.cloud/v1',
                    'disable_models_service': False,
                },
                'mcp': {'stdio': {'enabled': True}},
            }
        ),
    )
    persistence = PersistenceManager(application)
    application.persistence_mgr = persistence

    await persistence.initialize()
    try:
        application.workspace_service = WorkspaceService(
            application,
            instance_uuid=instance_uuid,
        )
        application.workspace_collaboration_service = WorkspaceCollaborationService(
            application,
            application.workspace_service,
        )
        application.user_service = UserService(application)

        quart_app = Quart(__name__)
        await UserRouterGroup(application, quart_app).initialize()
        await WorkspacesRouterGroup(application, quart_app).initialize()
        await SystemRouterGroup(application, quart_app).initialize()
        client = quart_app.test_client()

        initialization = await client.get('/api/v1/user/init')
        assert initialization.status_code == 200
        assert (await initialization.get_json())['data'] == {'initialized': False}

        initialized = await client.post(
            '/api/v1/user/init',
            json={'user': 'owner@example.com', 'password': 'owner-password'},
        )
        assert initialized.status_code == 200

        authenticated = await client.post(
            '/api/v1/user/auth',
            json={'user': 'owner@example.com', 'password': 'owner-password'},
        )
        assert authenticated.status_code == 200
        token = (await authenticated.get_json())['data']['token']

        bootstrap = await client.get(
            '/api/v1/workspaces/bootstrap',
            headers=_authorization(token),
        )
        assert bootstrap.status_code == 200
        bootstrap_workspaces = (await bootstrap.get_json())['data']['workspaces']
        assert len(bootstrap_workspaces) == 1
        bootstrap_access = bootstrap_workspaces[0]
        workspace_uuid = bootstrap_access['workspace']['uuid']
        assert bootstrap_access['workspace'] == {
            'uuid': workspace_uuid,
            'instance_uuid': instance_uuid,
            'name': 'Default Workspace',
            'slug': 'default',
            'type': 'team',
            'status': 'active',
            'source': 'local',
        }
        assert bootstrap_access['membership']['email'] == 'owner@example.com'
        assert bootstrap_access['membership']['role'] == 'owner'
        assert 'workspace.update' in bootstrap_access['permissions']

        current = await client.get(
            '/api/v1/workspaces/current',
            headers=_authorization(token, workspace_uuid),
        )
        assert current.status_code == 200
        current_data = (await current.get_json())['data']
        assert current_data['workspace']['uuid'] == workspace_uuid
        assert current_data['membership']['account_uuid'] == bootstrap_access['membership']['account_uuid']
        assert current_data['membership']['role'] == 'owner'

        user_info = await client.get(
            '/api/v1/user/info',
            headers=_authorization(token, workspace_uuid),
        )
        assert user_info.status_code == 200
        assert (await user_info.get_json())['data'] == {
            'account_uuid': bootstrap_access['membership']['account_uuid'],
            'user': 'owner@example.com',
            'account_type': 'local',
            'has_password': True,
        }

        initial_system_info = await client.get(
            '/api/v1/system/info',
            headers=_authorization(token, workspace_uuid),
        )
        assert initial_system_info.status_code == 200
        assert (await initial_system_info.get_json())['data']['wizard_status'] == 'none'
        assert (await initial_system_info.get_json())['data']['wizard_progress'] is None

        progress = {'step': 2, 'selected_adapter': 'telegram', 'bot_saved': False}
        updated_progress = await client.put(
            '/api/v1/system/wizard/progress',
            headers=_authorization(token, workspace_uuid),
            json=progress,
        )
        assert updated_progress.status_code == 200

        persisted_progress = await persistence.execute_async(
            sa.select(WorkspaceMetadata.value).where(
                WorkspaceMetadata.workspace_uuid == workspace_uuid,
                WorkspaceMetadata.key == 'wizard_progress',
            )
        )
        assert json.loads(persisted_progress.scalar_one()) == progress

        system_info_with_progress = await client.get(
            '/api/v1/system/info',
            headers=_authorization(token, workspace_uuid),
        )
        assert system_info_with_progress.status_code == 200
        progress_data = (await system_info_with_progress.get_json())['data']
        assert progress_data['wizard_status'] == 'none'
        assert progress_data['wizard_progress'] == progress

        completed = await client.post(
            '/api/v1/system/wizard/completed',
            headers=_authorization(token, workspace_uuid),
            json={'status': 'completed'},
        )
        assert completed.status_code == 200

        completed_system_info = await client.get(
            '/api/v1/system/info',
            headers=_authorization(token, workspace_uuid),
        )
        assert completed_system_info.status_code == 200
        completed_data = (await completed_system_info.get_json())['data']
        assert completed_data['wizard_status'] == 'completed'
        assert completed_data['wizard_progress'] is None

        rejected_workspace = await client.post(
            '/api/v1/workspaces',
            headers=_authorization(token, workspace_uuid),
            json={'name': 'Second Workspace'},
        )
        assert rejected_workspace.status_code == 403
        rejected_data = await rejected_workspace.get_json()
        assert rejected_data['code'] == 'edition_limit'

        persisted_wizard_status = await persistence.execute_async(
            sa.select(WorkspaceMetadata.value).where(
                WorkspaceMetadata.workspace_uuid == workspace_uuid,
                WorkspaceMetadata.key == 'wizard_status',
            )
        )
        assert persisted_wizard_status.scalar_one() == 'completed'
    finally:
        await persistence.get_db_engine().dispose()
