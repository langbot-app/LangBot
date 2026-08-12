"""Skills API behavior when a workspace plan has no managed sandbox."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.skills import SkillsRouterGroup
from langbot.pkg.cloud.entitlements import (
    EntitlementFeatureUnavailableError,
    EntitlementUnavailableError,
)

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
    application.deployment = SimpleNamespace(multi_workspace_enabled=False)
    application.persistence_mgr = SimpleNamespace(tenant_uow=None)
    application.user_service.get_authenticated_account = AsyncMock(return_value=account)
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(return_value=access)
    application.skill_service.list_skills = AsyncMock(
        side_effect=EntitlementFeatureUnavailableError(
            'managed_sandbox',
            entitlement_revision=1,
        )
    )

    quart_app = quart.Quart(__name__)
    router = SkillsRouterGroup(application, quart_app)
    await router.initialize()
    return application, quart_app.test_client()


@pytest.mark.asyncio
async def test_list_skills_is_empty_when_plan_has_no_managed_sandbox(skills_api):
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
    assert payload['data'] == {'skills': []}
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

    assert response.status_code == 500
