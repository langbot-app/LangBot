"""Plugin foundation contracts and Workspace isolation without a transport."""

from contextlib import asynccontextmanager
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zipfile import ZipFile

import pytest
from pydantic import TypeAdapter, ValidationError

from langbot.pkg.api.application import plugin_operations as ops
from langbot.pkg.api.context import ExecutionContext
from langbot.pkg.workspace.errors import WorkspaceGenerationMismatchError, WorkspaceNotFoundError


CONTEXT = SimpleNamespace(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=3)


def app():
    execution = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=3)
    return SimpleNamespace(
        plugin_connector=SimpleNamespace(require_workspace_context=AsyncMock(return_value=execution)),
        instance_config=SimpleNamespace(data={'system': {'limitation': {}}}),
    )


@pytest.mark.asyncio
async def test_plugin_reads_mask_secrets_and_config_write_restores_persisted_values():
    ap = app()
    raw = {'plugin_config': {'apiKey': 'runtime-secret'}, 'debug': {'plugin_debug_key': 'debug-secret'}}
    ap.plugin_connector.get_plugin_info = AsyncMock(return_value=raw)
    ap.plugin_connector.set_plugin_config = AsyncMock()
    ap.persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(
            return_value=SimpleNamespace(
                scalar_one_or_none=lambda: {
                    'apiKey': 'stored-secret',
                    'nested': {'token': 'nested-secret'},
                    'enabled': False,
                }
            )
        )
    )
    key = ops.PluginInput(author='a', plugin_name='b')
    assert (await ops.get_plugin(ap, CONTEXT, key))['plugin']['plugin_config']['apiKey'] == '***'
    assert raw['plugin_config']['apiKey'] == 'runtime-secret'
    assert (await ops.get_config(ap, CONTEXT, key))['config']['nested']['token'] == '***'
    await ops.update_config(
        ap,
        CONTEXT,
        ops.ConfigInput(
            author='a', plugin_name='b', config={'apiKey': '***', 'nested': {'token': '***'}, 'enabled': True}
        ),
    )
    assert ap.plugin_connector.set_plugin_config.await_args.args == (
        'a',
        'b',
        {'apiKey': 'stored-secret', 'nested': {'token': 'nested-secret'}, 'enabled': True},
    )
    with pytest.raises(ValueError, match='no existing value'):
        await ops.update_config(ap, CONTEXT, ops.ConfigInput(author='a', plugin_name='b', config={'password': '***'}))


@pytest.mark.asyncio
async def test_queued_plugin_task_revalidates_generation_before_runtime_io():
    ap = app()
    ap.plugin_connector.delete_plugin = AsyncMock()
    queued = []
    scopes = []

    @asynccontextmanager
    async def tenant_scope(workspace):
        scopes.append(workspace)
        yield

    def create_task(coro, **metadata):
        queued.append((coro, metadata))
        return SimpleNamespace(id=17)

    ap.persistence_mgr = SimpleNamespace(tenant_scope=tenant_scope)
    ap.task_mgr = SimpleNamespace(create_user_task=create_task)
    assert await ops.delete(ap, CONTEXT, ops.DeleteInput(author='a', plugin_name='b')) == {'task_id': 17}
    assert TypeAdapter(ops.TaskResult).validate_python({'task_id': 17}, strict=True) == {'task_id': 17}
    assert queued[0][1]['workspace_uuid'] == 'workspace-a'
    assert queued[0][1]['placement_generation'] == 3
    ap.plugin_connector.require_workspace_context.side_effect = WorkspaceGenerationMismatchError('stale placement')
    with pytest.raises(WorkspaceGenerationMismatchError):
        await queued[0][0]
    assert scopes == ['workspace-a']
    ap.plugin_connector.delete_plugin.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_quota_counts_plugins_and_mcp_before_queueing():
    ap = app()
    ap.instance_config.data['system']['limitation']['max_extensions'] = 2
    ap.plugin_connector.list_plugins = AsyncMock(return_value=[{}])
    ap.mcp_service = SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[{}]))
    ap.task_mgr = SimpleNamespace(create_user_task=Mock())
    with pytest.raises(ValueError, match='Maximum number'):
        await ops.install_marketplace(ap, CONTEXT, ops.MarketplaceInput(plugin_author='a', plugin_name='b'))
    ap.task_mgr.create_user_task.assert_not_called()


@pytest.mark.asyncio
async def test_asset_path_rejects_escape_before_runtime_read_and_returns_exact_bytes():
    ap = app()
    ap.plugin_connector.get_plugin_assets = AsyncMock(return_value={'asset_base64': 'AP8K', 'mime_type': 'image/png'})
    for path in ('../secret', '/etc/passwd', '..\\secret'):
        with pytest.raises(WorkspaceNotFoundError):
            await ops.asset(ap, CONTEXT, ops.AssetInput(author='a', plugin_name='b', filepath=path))
    ap.plugin_connector.get_plugin_assets.assert_not_awaited()
    result = await ops.asset(ap, CONTEXT, ops.AssetInput(author='a', plugin_name='b', filepath='image.png'))
    assert result == {'content': b'\x00\xff\n', 'mime_type': 'image/png'}
    assert ap.plugin_connector.get_plugin_assets.await_args.args == ('a', 'b', 'assets/image.png')


@pytest.mark.asyncio
async def test_config_files_are_workspace_scoped_and_size_checked():
    ap = app()
    ap.storage_mgr = SimpleNamespace(
        save_scoped=AsyncMock(return_value='scoped-key'),
        is_scoped_object_key=Mock(return_value=False),
        delete_scoped_object_key=AsyncMock(),
    )
    assert await ops.upload_config_file(ap, CONTEXT, ops.FileInput(content=b'payload', filename='data.txt')) == {
        'file_key': 'scoped-key'
    }
    args = ap.storage_mgr.save_scoped.await_args
    assert args.args == (CONTEXT,)
    assert args.kwargs['owner'] == 'workspace-a'
    assert args.kwargs['owner_type'] == 'plugin_config'
    assert args.kwargs['value'] == b'payload'
    with pytest.raises(ValueError, match='10MB'):
        await ops.upload_config_file(ap, CONTEXT, ops.FileInput(content=b'x' * (10 * 1024 * 1024 + 1)))
    with pytest.raises(ValueError, match='Invalid file key'):
        await ops.delete_config_file(ap, CONTEXT, ops.FileKeyInput(file_key='foreign/raw'))
    ap.storage_mgr.delete_scoped_object_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_preview_uses_archive_admission_and_component_metadata():
    ap = app()
    archive = BytesIO()
    with ZipFile(archive, 'w') as output:
        output.writestr(
            'manifest.yaml',
            'metadata:\n  author: example\n  name: sample\nspec:\n  components:\n    tools:\n      fromDirs: [components/tools]\n',
        )
        output.writestr('components/tools/tool.yaml', 'name: test')
        output.writestr('requirements.txt', 'httpx\n')
    result = await ops.preview_local(ap, CONTEXT, ops.FileInput(content=archive.getvalue(), filename='sample.lbpkg'))
    assert result['metadata'] == {'author': 'example', 'name': 'sample'}
    assert result['component_counts'] == {'tools': 1}
    assert result['requirements'] == ['httpx']
    with pytest.raises(ValueError):
        await ops.preview_local(ap, CONTEXT, ops.FileInput(content=b'invalid'))


def test_install_inputs_do_not_coerce_force_flags_or_github_path_segments():
    with pytest.raises(ValidationError):
        ops.LocalInstallInput(content=b'zip', administrator_force='true')
    with pytest.raises(ValidationError):
        ops.GithubAssetsInput(owner='a/b', repo='repo', release_id=1)
    with pytest.raises(ValidationError):
        ops.DeleteInput(author='a', plugin_name='b', delete_data='false')
