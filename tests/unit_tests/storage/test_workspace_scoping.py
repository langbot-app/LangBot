from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.storage.provider import HARD_MAX_STORAGE_OBJECT_BYTES
from langbot.pkg.utils.bounded_executor import current_blocking_work_scope


WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'


def _context(workspace_uuid: str, generation: int = 7) -> ExecutionContext:
    return ExecutionContext(
        instance_uuid='instance',
        workspace_uuid=workspace_uuid,
        placement_generation=generation,
    )


def _context_for_instance(instance_uuid: str) -> ExecutionContext:
    return ExecutionContext(
        instance_uuid=instance_uuid,
        workspace_uuid=WORKSPACE_A,
        placement_generation=7,
    )


class _Provider:
    def __init__(self):
        self.values: dict[str, bytes] = {}
        self.observed_public_scopes: list[str | None] = []

    async def save(self, key: str, value: bytes):
        self.values[key] = value

    async def load(self, key: str) -> bytes:
        self.observed_public_scopes.append(current_blocking_work_scope())
        return self.values[key]

    async def exists(self, key: str) -> bool:
        self.observed_public_scopes.append(current_blocking_work_scope())
        return key in self.values

    async def size(self, key: str) -> int:
        return len(self.values[key])

    async def delete(self, key: str):
        self.values.pop(key, None)


class _WorkspaceService:
    instance_uuid = 'instance'

    async def get_execution_binding(self, workspace_uuid, expected_generation=None):
        if workspace_uuid not in {WORKSPACE_A, WORKSPACE_B} or expected_generation != 7:
            raise ValueError('inactive or stale binding')
        return SimpleNamespace(
            instance_uuid='instance',
            workspace_uuid=workspace_uuid,
            placement_generation=7,
        )


@pytest.fixture
def manager():
    application = SimpleNamespace(workspace_service=_WorkspaceService())
    storage = StorageMgr(application)
    storage.storage_provider = _Provider()
    return storage


def test_binary_storage_canonical_key_covers_every_scope_dimension(manager):
    baseline = manager.canonical_binary_storage_key(
        _context(WORKSPACE_A),
        owner_type='plugin',
        owner='author/name',
        key='same-key',
    )
    assert baseline != manager.canonical_binary_storage_key(
        _context(WORKSPACE_B),
        owner_type='plugin',
        owner='author/name',
        key='same-key',
    )
    assert baseline != manager.canonical_binary_storage_key(
        _context_for_instance('other-instance'),
        owner_type='plugin',
        owner='author/name',
        key='same-key',
    )
    assert baseline != manager.canonical_binary_storage_key(
        _context(WORKSPACE_A),
        owner_type='workspace',
        owner='author/name',
        key='same-key',
    )
    assert baseline != manager.canonical_binary_storage_key(
        _context(WORKSPACE_A),
        owner_type='plugin',
        owner='other/name',
        key='same-key',
    )
    assert baseline != manager.canonical_binary_storage_key(
        _context(WORKSPACE_A),
        owner_type='plugin',
        owner='author/name',
        key='other-key',
    )


@pytest.mark.asyncio
async def test_public_object_route_derives_trusted_workspace(manager):
    object_key = await manager.save_scoped(
        _context(WORKSPACE_A),
        owner_type='upload',
        owner='account:a',
        key='photo.png',
        value=b'image-a',
    )
    assert await manager.resolve_public_object(object_key, expected_owner_type='upload') == b'image-a'
    assert manager.storage_provider.observed_public_scopes[-2:] == [
        WORKSPACE_A,
        WORKSPACE_A,
    ]
    assert await manager.resolve_public_object(object_key, expected_owner_type='plugin') is None

    guessed_workspace_key = object_key.replace(WORKSPACE_A, WORKSPACE_B)
    assert await manager.resolve_public_object(guessed_workspace_key, expected_owner_type='upload') is None

    stale_generation_key = object_key.replace('/7/upload/', '/8/upload/')
    assert await manager.resolve_public_object(stale_generation_key, expected_owner_type='upload') is None


@pytest.mark.asyncio
async def test_storage_operations_without_context_fail_closed(manager):
    with pytest.raises(WorkspaceRequiredError):
        await manager.save_scoped(
            None,
            owner_type='upload',
            owner='account:a',
            key='photo.png',
            value=b'image',
        )


@pytest.mark.asyncio
async def test_opaque_object_operations_reject_cross_scope_and_owner_type(manager):
    object_key = await manager.save_scoped(
        _context(WORKSPACE_A),
        owner_type='upload',
        owner='account:a',
        key='document.pdf',
        value=b'document-a',
    )

    assert await manager.exists_scoped_object_key(
        _context(WORKSPACE_A),
        object_key,
        expected_owner_type='upload',
    )
    assert (
        await manager.load_scoped_object_key(
            _context(WORKSPACE_A),
            object_key,
            expected_owner_type='upload',
        )
        == b'document-a'
    )
    assert await manager.size_scoped_object_key(
        _context(WORKSPACE_A),
        object_key,
        expected_owner_type='upload',
    ) == len(b'document-a')

    for wrong_context in (_context(WORKSPACE_B), _context(WORKSPACE_A, generation=8)):
        with pytest.raises(WorkspaceRequiredError):
            await manager.load_scoped_object_key(
                wrong_context,
                object_key,
                expected_owner_type='upload',
            )
        with pytest.raises(WorkspaceRequiredError):
            await manager.delete_scoped_object_key(
                wrong_context,
                object_key,
                expected_owner_type='upload',
            )

    with pytest.raises(WorkspaceRequiredError):
        await manager.load_scoped_object_key(
            _context(WORKSPACE_A),
            object_key,
            expected_owner_type='plugin_config',
        )

    assert object_key in manager.storage_provider.values


@pytest.mark.asyncio
async def test_scoped_object_reads_and_writes_have_configured_and_hard_byte_limits(manager):
    manager.ap.instance_config = SimpleNamespace(data={'storage': {'max_object_read_bytes': 4}})

    with pytest.raises(ValueError, match='4-byte write limit'):
        await manager.save_scoped(
            _context(WORKSPACE_A),
            owner_type='upload',
            owner='account:a',
            key='oversized.bin',
            value=b'12345',
        )

    object_key = manager.scoped_object_key(
        _context(WORKSPACE_A),
        owner_type='upload',
        owner='account:a',
        key='external.bin',
    )
    manager.storage_provider.values[object_key] = b'12345'
    manager.storage_provider.load = AsyncMock(side_effect=AssertionError('oversized object must not be loaded'))
    with pytest.raises(ValueError, match='4-byte read limit'):
        await manager.load_scoped_object_key(
            _context(WORKSPACE_A),
            object_key,
            expected_owner_type='upload',
        )
    manager.storage_provider.load.assert_not_awaited()

    manager.ap.instance_config.data['storage']['max_object_read_bytes'] = HARD_MAX_STORAGE_OBJECT_BYTES + 1
    assert manager._object_read_limit() == HARD_MAX_STORAGE_OBJECT_BYTES


@pytest.mark.asyncio
async def test_scoped_provider_is_not_touched_after_generation_is_fenced(manager):
    object_key = await manager.save_scoped(
        _context(WORKSPACE_A),
        owner_type='upload',
        owner='account:a',
        key='document.pdf',
        value=b'document-a',
    )
    manager.ap.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(side_effect=ValueError('generation is stale'))
    )
    manager.storage_provider.load = AsyncMock(side_effect=AssertionError('provider must not be called'))

    with pytest.raises(WorkspaceRequiredError, match='execution scope is unavailable'):
        await manager.load_scoped_object_key(
            _context(WORKSPACE_A),
            object_key,
            expected_owner_type='upload',
        )
    manager.storage_provider.load.assert_not_awaited()


@pytest.mark.asyncio
async def test_scoped_provider_rejects_incomplete_execution_binding(manager):
    manager.ap.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance'))
    )
    manager.storage_provider.save = AsyncMock(side_effect=AssertionError('provider must not be called'))

    with pytest.raises(WorkspaceRequiredError, match='execution scope is unavailable'):
        await manager.save_scoped(
            _context(WORKSPACE_A),
            owner_type='upload',
            owner='account:a',
            key='document.pdf',
            value=b'document-a',
        )
    manager.storage_provider.save.assert_not_awaited()
