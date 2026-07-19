from __future__ import annotations

import datetime
import hashlib
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.plugin.connector import (
    PluginInstallationFailedError,
    PluginRuntimeConnector,
)


def connection_result_connector(execute_async: AsyncMock) -> PluginRuntimeConnector:
    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
        deployment=SimpleNamespace(mode='cloud'),
        persistence_mgr=SimpleNamespace(
            tenant_uow=None,
            execute_async=execute_async,
        ),
        logger=Mock(),
    )
    return PluginRuntimeConnector(app, AsyncMock())


def execution_binding(workspace_uuid: str, generation: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        instance_uuid='instance-a',
        workspace_uuid=workspace_uuid,
        placement_generation=generation,
    )


def plugin_setting(
    workspace_suffix: str,
    artifact_digest: str,
    *,
    durable: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        plugin_author='author',
        plugin_name=f'plugin-{workspace_suffix}',
        installation_uuid=f'00000000-0000-4000-8000-0000000000{workspace_suffix}',
        runtime_revision=1,
        artifact_digest=artifact_digest,
        enabled=True,
        priority=0,
        created_at=datetime.datetime(2026, 1, 1),
        install_source='local',
        install_info={'_artifact_storage': 'tenant_binary_storage_v1'} if durable else {},
    )


def runtime_handler(
    *,
    missing_artifacts: list[str] | None = None,
    failed_installations: list[dict[str, str]] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        register_installation_binding=Mock(),
        unregister_installation_binding=Mock(),
        reconcile_plugin_installations=AsyncMock(
            return_value={
                'applied': [],
                'removed': [],
                'missing_artifacts': missing_artifacts or [],
                'failed_installations': failed_installations or [],
            }
        ),
        apply_plugin_installation=AsyncMock(return_value={'state': 'starting'}),
        installation_scope=Mock(side_effect=lambda _binding: nullcontext()),
        list_plugins=AsyncMock(return_value=[]),
    )


def shared_connector(
    projected_bindings: list[list[SimpleNamespace]],
    settings: dict[str, list[SimpleNamespace]],
) -> PluginRuntimeConnector:
    async def get_execution_binding(workspace_uuid: str, *, expected_generation: int | None = None):
        for binding_set in projected_bindings:
            for binding in binding_set:
                if binding.workspace_uuid == workspace_uuid:
                    assert expected_generation in (None, binding.placement_generation)
                    return binding
        raise AssertionError(f'unexpected Workspace {workspace_uuid}')

    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
        deployment=SimpleNamespace(mode='cloud'),
        workspace_service=SimpleNamespace(
            list_active_execution_bindings=AsyncMock(side_effect=projected_bindings),
            get_execution_binding=AsyncMock(side_effect=get_execution_binding),
        ),
        persistence_mgr=SimpleNamespace(tenant_uow=None),
        logger=Mock(),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    connector._load_workspace_settings = AsyncMock(side_effect=lambda context: settings[context.workspace_uuid])
    return connector


@pytest.mark.asyncio
async def test_shared_reconnect_replays_two_workspaces_and_removes_missing_projection():
    binding_a = execution_binding('workspace-a')
    binding_b = execution_binding('workspace-b')
    setting_a = plugin_setting('01', 'a' * 64)
    setting_b = plugin_setting('02', 'b' * 64)
    connector = shared_connector(
        [[binding_a, binding_b], [binding_a]],
        {'workspace-a': [setting_a], 'workspace-b': [setting_b]},
    )

    first_handler = runtime_handler()
    connector.handler = first_handler
    await connector._prepare_connected_runtime()

    first_desired = first_handler.reconcile_plugin_installations.await_args.args[0]
    assert {state.binding.workspace_uuid for state in first_desired} == {'workspace-a', 'workspace-b'}

    second_handler = runtime_handler()
    connector.handler = second_handler
    await connector._prepare_connected_runtime()

    second_desired = second_handler.reconcile_plugin_installations.await_args.args[0]
    assert [state.binding.workspace_uuid for state in second_desired] == ['workspace-a']
    second_handler.unregister_installation_binding.assert_called_once_with(first_desired[1].binding)
    assert set(connector._workspace_installations) == {'workspace-a'}
    assert set(connector._known_desired_states) == {setting_a.installation_uuid}


@pytest.mark.asyncio
async def test_fresh_shared_runtime_cache_replays_persisted_local_package():
    package = b'local-lbpkg-bytes'
    digest = hashlib.sha256(package).hexdigest()
    binding = execution_binding('workspace-a')
    setting = plugin_setting('01', digest)
    connector = shared_connector([[binding]], {'workspace-a': [setting]})
    connector.handler = runtime_handler(missing_artifacts=[setting.installation_uuid])
    connector._load_artifact_package = AsyncMock(return_value=package)

    await connector._prepare_connected_runtime()

    desired = connector.handler.reconcile_plugin_installations.await_args.args[0][0]
    connector._load_artifact_package.assert_awaited_once()
    connector.handler.apply_plugin_installation.assert_awaited_once_with(
        desired.binding,
        artifact_package=package,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_oss_upgrade_keeps_legacy_data_plugins_when_no_lbpkg_was_backfilled():
    binding = execution_binding('workspace-a')
    setting = plugin_setting('01', hashlib.sha256(b'legacy-installation').hexdigest(), durable=False)
    legacy_plugin = {
        'debug': False,
        'manifest': {'manifest': {'metadata': {'author': 'author', 'name': 'plugin-01'}}},
        'components': [],
    }
    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
        deployment=SimpleNamespace(mode='oss'),
        workspace_service=SimpleNamespace(get_local_execution_binding=AsyncMock(return_value=binding)),
        persistence_mgr=SimpleNamespace(tenant_uow=None),
        logger=Mock(),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    connector.handler = runtime_handler(missing_artifacts=[setting.installation_uuid])
    connector.handler.list_plugins = AsyncMock(return_value=[legacy_plugin])
    connector.handler.apply_plugin_installation = AsyncMock(return_value={'state': 'artifact_missing'})
    connector._load_workspace_settings = AsyncMock(return_value=[setting])
    connector._load_artifact_package = AsyncMock(return_value=None)

    await connector._prepare_connected_runtime()
    plugins = await connector.list_plugins()

    assert plugins == [legacy_plugin]
    assert connector.handler.list_plugins.await_count >= 2
    connector._load_artifact_package.assert_awaited_once()
    assert not hasattr(connector.handler, 'delete_plugin')


@pytest.mark.asyncio
async def test_local_install_persists_verified_package_before_runtime_apply():
    package = b'local-lbpkg-bytes'
    digest = hashlib.sha256(package).hexdigest()
    execution_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
    )
    binding = InstallationBinding(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=1,
        artifact_digest=digest,
    )
    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
        deployment=SimpleNamespace(mode='cloud'),
        logger=Mock(),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    connector.handler = runtime_handler()
    connector._current_execution_context = AsyncMock(return_value=execution_context)
    connector._inspect_plugin_package = Mock(return_value=('author', 'plugin'))
    connector._store_artifact_package = AsyncMock()
    connector._persist_installation_package = AsyncMock(return_value=(binding, None, False))
    connector._wait_for_installed_plugin_ready = AsyncMock()

    await connector.install_plugin(
        PluginInstallSource.LOCAL,
        {'plugin_file': package},
    )

    connector._store_artifact_package.assert_awaited_once_with(execution_context, digest, package)
    connector.handler.apply_plugin_installation.assert_awaited_once_with(
        binding,
        artifact_package=package,
        enabled=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(('remaining_references', 'statement_count'), [(1, 1), (0, 2)])
async def test_artifact_cleanup_is_reference_counted_within_workspace(
    remaining_references: int,
    statement_count: int,
):
    app = SimpleNamespace(
        instance_config=SimpleNamespace(data={'plugin': {'enable': True}}),
        deployment=SimpleNamespace(mode='cloud'),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    execution_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
    )
    statements = []

    async def execute(statement):
        statements.append(statement)
        return SimpleNamespace(scalar_one=lambda: remaining_references)

    await connector._delete_artifact_if_unreferenced(
        execution_context,
        'a' * 64,
        execute=execute,
    )

    assert len(statements) == statement_count


@pytest.mark.asyncio
async def test_artifact_store_and_load_accept_connection_scalar_results():
    package = b'persisted-lbpkg'
    digest = hashlib.sha256(package).hexdigest()
    execution_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
    )
    execute_async = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: package))
    connector = connection_result_connector(execute_async)

    await connector._store_artifact_package(execution_context, digest, package)
    loaded = await connector._load_artifact_package(execution_context, digest)

    assert loaded == package
    assert execute_async.await_count == 2


@pytest.mark.asyncio
async def test_workspace_settings_accept_connection_mapping_results():
    created_at = datetime.datetime(2026, 1, 1)
    row = {
        'workspace_uuid': 'workspace-a',
        'plugin_author': 'author',
        'plugin_name': 'plugin',
        'installation_uuid': '00000000-0000-4000-8000-000000000001',
        'artifact_digest': 'a' * 64,
        'runtime_revision': 2,
        'enabled': True,
        'priority': 3,
        'config': {'key': 'value'},
        'install_source': 'local',
        'install_info': {'_artifact_storage': 'tenant_binary_storage_v1'},
        'created_at': created_at,
        'updated_at': created_at,
    }
    mapped_result = SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [row]))
    connector = connection_result_connector(AsyncMock(return_value=mapped_result))

    settings = await connector._load_workspace_settings(
        ExecutionContext(
            instance_uuid='instance-a',
            workspace_uuid='workspace-a',
            placement_generation=1,
        )
    )

    assert len(settings) == 1
    assert settings[0].installation_uuid == row['installation_uuid']
    assert settings[0].runtime_revision == 2
    assert settings[0].created_at == created_at


@pytest.mark.asyncio
async def test_installation_update_accepts_connection_row_result():
    old_digest = 'a' * 64
    new_digest = 'b' * 64
    existing = SimpleNamespace(
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=4,
        artifact_digest=old_digest,
        install_info={'_artifact_storage': 'tenant_binary_storage_v1'},
    )
    execute_async = AsyncMock(
        side_effect=[
            SimpleNamespace(first=lambda: existing),
            SimpleNamespace(rowcount=1),
        ]
    )
    connector = connection_result_connector(execute_async)
    execution_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=7,
    )

    binding, previous_digest, previous_was_durable = await connector._persist_installation_package(
        execution_context,
        plugin_author='author',
        plugin_name='plugin',
        install_source=PluginInstallSource.LOCAL,
        install_info={},
        artifact_digest=new_digest,
    )

    assert binding.installation_uuid == existing.installation_uuid
    assert binding.runtime_revision == 5
    assert binding.artifact_digest == new_digest
    assert previous_digest == old_digest
    assert previous_was_durable is True


@pytest.mark.asyncio
async def test_apply_dependency_failure_raises_stable_observable_error():
    binding = execution_binding('workspace-a')
    setting = plugin_setting('01', 'a' * 64)
    connector = shared_connector([[binding]], {'workspace-a': [setting]})
    connector.handler = runtime_handler()
    desired = (
        await connector._load_workspace_desired_states(
            ExecutionContext(
                instance_uuid='instance-a',
                workspace_uuid='workspace-a',
                placement_generation=1,
            )
        )
    )[0]
    connector.handler.apply_plugin_installation.return_value = {
        'installation_uuid': setting.installation_uuid,
        'state': 'failed',
        'error_code': 'dependency_prepare_failed',
        'message': 'Plugin dependency installer exited with code 1',
    }

    with pytest.raises(PluginInstallationFailedError) as exc_info:
        await connector._apply_desired_state(desired)

    error = exc_info.value
    assert error.installation_uuid == setting.installation_uuid
    assert error.error_code == 'dependency_prepare_failed'
    assert '[dependency_prepare_failed]' in str(error)
    assert connector._installation_failures[setting.installation_uuid] == {
        'installation_uuid': setting.installation_uuid,
        'error_code': 'dependency_prepare_failed',
        'message': 'Plugin dependency installer exited with code 1',
    }
    connector.ap.logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_shared_reconcile_records_one_failure_without_blocking_other_state():
    binding_a = execution_binding('workspace-a')
    binding_b = execution_binding('workspace-b')
    setting_a = plugin_setting('01', 'a' * 64)
    setting_b = plugin_setting('02', 'b' * 64)
    failure = {
        'installation_uuid': setting_a.installation_uuid,
        'error_code': 'dependency_prepare_failed',
        'message': 'Plugin dependency installer exited with code 1',
    }
    connector = shared_connector(
        [[binding_a, binding_b]],
        {'workspace-a': [setting_a], 'workspace-b': [setting_b]},
    )
    connector.handler = runtime_handler(failed_installations=[failure])

    await connector._prepare_connected_runtime()

    desired = connector.handler.reconcile_plugin_installations.await_args.args[0]
    assert {item.binding.installation_uuid for item in desired} == {
        setting_a.installation_uuid,
        setting_b.installation_uuid,
    }
    assert connector._installation_failures == {
        setting_a.installation_uuid: failure,
    }
    assert set(connector._known_desired_states) == {
        setting_a.installation_uuid,
        setting_b.installation_uuid,
    }
    connector.ap.logger.error.assert_called_once_with(
        'Plugin installation %s failed during reconcile [%s]: %s',
        setting_a.installation_uuid,
        'dependency_prepare_failed',
        'Plugin dependency installer exited with code 1',
    )


@pytest.mark.asyncio
async def test_missing_artifact_repair_adds_dependency_failure_and_continues():
    package_a = b'package-a'
    package_b = b'package-b'
    binding = execution_binding('workspace-a')
    setting_a = plugin_setting('01', hashlib.sha256(package_a).hexdigest())
    setting_b = plugin_setting('02', hashlib.sha256(package_b).hexdigest())
    connector = shared_connector(
        [[binding]],
        {'workspace-a': [setting_a, setting_b]},
    )
    connector.handler = runtime_handler(
        missing_artifacts=[
            setting_a.installation_uuid,
            setting_b.installation_uuid,
        ]
    )
    connector._load_artifact_package = AsyncMock(side_effect=[package_a, package_b])
    connector.handler.apply_plugin_installation.side_effect = [
        {
            'installation_uuid': setting_a.installation_uuid,
            'state': 'failed',
            'error_code': 'dependency_prepare_failed',
            'message': 'Plugin dependency installer exited with code 1',
        },
        {'installation_uuid': setting_b.installation_uuid, 'state': 'starting'},
    ]

    result = await connector.reconcile_projected_workspaces(
        [
            ExecutionContext(
                instance_uuid='instance-a',
                workspace_uuid='workspace-a',
                placement_generation=1,
            )
        ]
    )

    assert connector.handler.apply_plugin_installation.await_count == 2
    assert result['failed_installations'] == [
        {
            'installation_uuid': setting_a.installation_uuid,
            'error_code': 'dependency_prepare_failed',
            'message': 'Plugin dependency installer exited with code 1',
        }
    ]
    assert setting_a.installation_uuid in connector._installation_failures
    assert setting_b.installation_uuid not in connector._installation_failures
