from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart
from quart.datastructures import FileStorage

from langbot.pkg.api.http.controller.groups.files import FilesRouterGroup


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
    storage_mgr = SimpleNamespace(save_scoped=AsyncMock(return_value='scoped-document-key'))
    application = SimpleNamespace(
        user_service=SimpleNamespace(get_authenticated_account=AsyncMock(return_value=account)),
        workspace_collaboration_service=SimpleNamespace(resolve_account_workspace=AsyncMock(return_value=access)),
        storage_mgr=storage_mgr,
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
    assert (await response.get_json())['data']['file_id'] == 'scoped-document-key'
    kwargs = storage_mgr.save_scoped.await_args.kwargs
    assert kwargs['owner_type'] == 'upload_document'
    assert kwargs['owner'] == 'account:account-test'
    assert kwargs['key'].endswith('.pdf')
    assert kwargs['value'] == b'document bytes'
