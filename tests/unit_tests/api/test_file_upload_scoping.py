from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart
from quart.datastructures import FileStorage

from langbot.pkg.api.http.controller.groups.files import FilesRouterGroup
from langbot.pkg.api.http.context import RequestContext


pytestmark = pytest.mark.asyncio


async def test_document_upload_uses_dedicated_scoped_owner_type():
    quart_app = quart.Quart(__name__)
    account = SimpleNamespace(uuid='account-test', user='test@example.com')
    access = SimpleNamespace(
        execution=SimpleNamespace(
            instance_uuid='instance-test',
            placement_generation=3,
        ),
        workspace=SimpleNamespace(uuid='00000000-0000-0000-0000-00000000000a'),
        membership=SimpleNamespace(
            uuid='membership-test',
            role='developer',
            projection_revision=1,
        ),
    )
    artifact_service = SimpleNamespace(
        create_legacy_upload=AsyncMock(return_value={'file_key': 'scoped-document-key', 'artifact': {'id': 'art_test'}})
    )
    application = SimpleNamespace(
        user_service=SimpleNamespace(get_authenticated_account=AsyncMock(return_value=account)),
        workspace_collaboration_service=SimpleNamespace(resolve_account_workspace=AsyncMock(return_value=access)),
        artifact_service=artifact_service,
    )
    router = FilesRouterGroup(application, quart_app)
    await router.initialize()
    client = quart_app.test_client()

    response = await client.post(
        '/api/v1/files/documents',
        headers={'Authorization': 'Bearer test-token'},
        files={
            'file': FileStorage(
                stream=io.BytesIO(b'document bytes'),
                filename='report.pdf',
            )
        },
    )

    assert response.status_code == 200
    assert (await response.get_json())['data'] == {'file_id': 'scoped-document-key', 'artifact_id': 'art_test'}
    artifact_service.create_legacy_upload.assert_awaited_once()
    context = artifact_service.create_legacy_upload.await_args.args[0]
    assert isinstance(context, RequestContext)
    assert context.instance_uuid == 'instance-test'
    assert context.workspace_uuid == '00000000-0000-0000-0000-00000000000a'
    assert context.placement_generation == 3
    assert context.account_uuid == 'account-test'
    kwargs = artifact_service.create_legacy_upload.await_args.kwargs
    assert kwargs['owner_type'] == 'upload_document'
    assert kwargs['owner'] == 'account:account-test'
    assert kwargs['key'].endswith('.pdf')
    assert kwargs['value'] == b'document bytes'
