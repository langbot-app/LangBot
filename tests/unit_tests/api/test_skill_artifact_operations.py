"""Skill source references stay behind the account ApplicationAPI boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from langbot.pkg.api.application.artifact_operations import (
    SkillResourceArtifactCreate,
    create_skill_resource,
    operations,
)
from langbot.pkg.api.application.operation_docs import get_operation_doc
from langbot.pkg.api.context import PrincipalType
from langbot.pkg.api.authz import Permission


def test_source_operation_is_not_a_plugin_or_default_model_grant():
    operation = next(op for op in operations() if op.operation_id == 'artifact.skill_resource.create')
    assert operation.principals == frozenset({PrincipalType.ACCOUNT, PrincipalType.API_KEY})
    assert operation.permission == Permission.RESOURCE_MANAGE
    assert operation.side_effect
    assert get_operation_doc(operation.operation_id).exposure == 'none'


@pytest.mark.parametrize(
    'payload',
    [
        {'skill_name': 'demo', 'path': 'file.txt'},
        {'skill_name': 'demo', 'revision': '', 'path': 'file.txt'},
        {'skill_name': 'demo', 'revision': 'v1', 'path': ''},
        {'skill_name': 'demo', 'revision': 'v1', 'path': 'file.txt', 'storage_key': 'private'},
    ],
)
def test_fixed_revision_required_and_storage_keys_not_accepted(payload):
    with pytest.raises(ValidationError):
        SkillResourceArtifactCreate(**payload)


@pytest.mark.asyncio
async def test_service_receives_trusted_context_and_validated_payload():
    service = SimpleNamespace(create_skill_resource=AsyncMock(return_value={'id': 'art_example'}))
    context = object()
    payload = SkillResourceArtifactCreate(skill_name='demo', revision='v1', path='file.txt')
    assert await create_skill_resource(SimpleNamespace(artifact_service=service), context, payload) == {
        'id': 'art_example'
    }
    service.create_skill_resource.assert_awaited_once_with(
        context, skill_name='demo', revision='v1', path='file.txt', ttl_seconds=86400
    )
