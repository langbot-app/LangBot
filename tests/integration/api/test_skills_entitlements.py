"""Skills API behavior is independent from managed sandbox entitlement."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.skills import SkillsRouterGroup
from langbot.pkg.api.http.service.skill import SkillService
from langbot.pkg.cloud.entitlements import EntitlementUnavailableError
from langbot.pkg.skill.repository import SkillRepository

pytestmark = pytest.mark.integration
WORKSPACE_UUID = '11111111-1111-4111-8111-111111111111'


@pytest.fixture
async def skills_api():
    account = SimpleNamespace(uuid='owner-account', user='owner@example.com')
    access = SimpleNamespace(
        workspace=SimpleNamespace(uuid=WORKSPACE_UUID),
        membership=SimpleNamespace(uuid='member-owner', role='owner', projection_revision=1),
        execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
    )
    application = Mock()
    application._message_language_cache = None
    application.deployment = SimpleNamespace(multi_workspace_enabled=False)
    application.persistence_mgr = SimpleNamespace(tenant_uow=None)
    application.user_service.get_authenticated_account = AsyncMock(return_value=account)
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(return_value=access)
    application.skill_service.list_skills = AsyncMock(
        return_value=[{'name': 'docs-only', 'description': 'No execution required'}]
    )

    quart_app = quart.Quart(__name__)
    router = SkillsRouterGroup(application, quart_app)
    await router.initialize()
    return application, quart_app.test_client()


@pytest.mark.asyncio
async def test_list_skills_remains_available_without_managed_sandbox(skills_api):
    application, client = skills_api
    response = await client.get(
        '/api/v1/skills',
        headers={
            'Authorization': 'Bearer owner-token',
            'X-Workspace-Id': WORKSPACE_UUID,
        },
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['data'] == {'skills': [{'name': 'docs-only', 'description': 'No execution required'}]}
    application.skill_service.list_skills.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_skills_does_not_hide_other_entitlement_failures(skills_api):
    application, client = skills_api
    application.skill_service.list_skills.side_effect = EntitlementUnavailableError(
        'Workspace entitlement revision rolled back'
    )

    response = await client.get(
        '/api/v1/skills',
        headers={
            'Authorization': 'Bearer owner-token',
            'X-Workspace-Id': WORKSPACE_UUID,
        },
    )

    assert response.status_code == 403
    payload = await response.get_json()
    assert payload['code'] == 'entitlement_unavailable'


@pytest.mark.asyncio
async def test_skill_file_write_returns_conflict_without_replacing_saved_content(skills_api, tmp_path):
    application, client = skills_api
    application.instance_config = SimpleNamespace(data={'skills': {'root': str(tmp_path / 'skills')}})
    application.workspace_service.get_execution_binding = AsyncMock(
        return_value=SimpleNamespace(instance_uuid='instance-a', workspace_uuid=WORKSPACE_UUID, placement_generation=1)
    )
    application.skill_mgr = SimpleNamespace(reload_skills=AsyncMock())
    application.skill_repository = SkillRepository(application)
    application.skill_service = SkillService(application)
    headers = {'Authorization': 'Bearer owner-token', 'X-Workspace-Id': WORKSPACE_UUID}

    created = await client.post(
        '/api/v1/skills',
        headers=headers,
        json={'name': 'editable', 'instructions': 'Keep these instructions.'},
    )
    assert created.status_code == 200
    original_revision = (await created.get_json())['data']['skill']['revision']
    path = '/api/v1/skills/editable/files/references/guide.md'
    written = await client.put(path, headers=headers, json={'content': 'Saved content', 'base_revision': original_revision})
    assert written.status_code == 200
    revision = (await written.get_json())['data']['revision']
    assert revision.startswith('sha256:') and revision != original_revision

    stale = await client.put(path, headers=headers, json={'content': 'Stale overwrite', 'base_revision': original_revision})
    assert stale.status_code == 409
    saved = await client.get(path, headers=headers)
    assert saved.status_code == 200
    assert (await saved.get_json())['data']['content'] == 'Saved content'
    current = await client.get('/api/v1/skills/editable', headers=headers)
    skill = (await current.get_json())['data']['skill']
    assert skill['revision'] == revision
    assert skill['instructions'] == 'Keep these instructions.'
