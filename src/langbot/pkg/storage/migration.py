"""Offline, resumable import of retained local uploads and public media."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from contextlib import ExitStack

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..api.http.context import ExecutionContext
from ..entity.persistence.content import ContentAlias, ContentObject
from ..persistence.legacy_migration import WorkspaceMigration, require_import_runtime
from ..utils.bounded_executor import blocking_work_scope, run_blocking_atomic
from .media import SAFE_MEDIA_FILENAME
from .mgr import StorageMgr, _SCOPED_KEY
from .provider import HARD_MAX_STORAGE_OBJECT_BYTES
from .providers import localstorage


_DOMAIN = 'storage-filesystem-v1'
# shortcut: inventory is capped at 100000 entries; stream it before supporting larger legacy stores.
_MAX_SOURCE_ENTRIES = 100000


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _inventory(root, contexts, public_workspace):
    """Reject unmapped legacy layouts before importing any Workspace."""
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError('Legacy storage root must be a link-free directory')
    scopes = {(StorageMgr._digest(c.instance_uuid, 24), c.workspace_uuid) for c in contexts}
    result = []
    remaining = [_MAX_SOURCE_ENTRIES]

    def entries(path):
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise ValueError('Legacy storage contains an unsafe directory')
        with os.scandir(path) as iterator:
            names = []
            for entry in iterator:
                remaining[0] -= 1
                if remaining[0] < 0:
                    raise ValueError('Legacy storage inventory exceeds 100000 entries')
                names.append(entry.name)
        return [path / name for name in sorted(names)]

    def walk(directory, workspace, depth=0):
        if depth > 4:
            raise ValueError('Legacy storage has an unsupported directory depth')
        for path in entries(directory):
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                walk(path, workspace, depth + 1)
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Legacy storage requires regular files without links')
            key = path.relative_to(root).as_posix()
            if key.startswith('media_cache/'):
                if not SAFE_MEDIA_FILENAME.fullmatch(path.name) or len(path.relative_to(root).parts) != 2:
                    raise ValueError('Legacy public media has an invalid key')
                if workspace is None:
                    raise ValueError('Legacy public media requires an OSS singleton Workspace')
            else:
                match = _SCOPED_KEY.fullmatch(key)
                if match is None or (match['instance'], match['workspace']) not in scopes:
                    raise ValueError('Legacy upload key does not match an active Workspace')
            if info.st_size > HARD_MAX_STORAGE_OBJECT_BYTES:
                raise ValueError('Legacy storage object exceeds the 64 MiB import limit')
            result.append((key, _identity(info), workspace))

    for path in entries(root):
        if path.name == 'media_cache':
            walk(path, public_workspace)
        elif path.name == 'v1':
            for instance in entries(path):
                if not any(instance.name == item[0] for item in scopes):
                    raise ValueError('Legacy uploads belong to an unknown instance; restore system.instance_id')
                for workspace in entries(instance):
                    if (instance.name, workspace.name) not in scopes:
                        raise ValueError('Legacy uploads belong to an unknown or inactive Workspace')
                    walk(workspace, workspace.name)
        else:
            raise ValueError('Unsupported legacy storage layout; retain the old provider or migrate it explicitly')
    result.sort()
    fingerprint = hashlib.sha256()
    for key, identity, _workspace in result:
        fingerprint.update(json.dumps([key, identity[2], identity[3]], separators=(',', ':')).encode())
        fingerprint.update(b'\n')
    return result, fingerprint.hexdigest(), str(root.resolve())


def _read_source(root, key, expected):
    path = root.joinpath(*key.split('/'))
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Legacy storage path escapes its source root')
    if _identity(path.lstat()) != expected:
        raise ValueError('Legacy storage changed during import')
    if os.open not in os.supports_dir_fd or not hasattr(os, 'O_NOFOLLOW'):
        raise ValueError('Legacy storage import requires descriptor-relative no-follow filesystem access')
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as opened:
        directory = os.open(root, directory_flags)
        opened.callback(os.close, directory)
        parts = key.split('/')
        for part in parts[:-1]:
            directory = os.open(part, directory_flags, dir_fd=directory)
            opened.callback(os.close, directory)
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0)
        with os.fdopen(os.open(parts[-1], flags, dir_fd=directory), 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or _identity(info) != expected:
                raise ValueError('Legacy storage changed while opening an object')
            value = source.read(HARD_MAX_STORAGE_OBJECT_BYTES + 1)
            if len(value) > HARD_MAX_STORAGE_OBJECT_BYTES or len(value) != info.st_size:
                raise ValueError('Legacy storage object changed or exceeds the import size limit')
            if _identity(os.fstat(source.fileno())) != expected:
                raise ValueError('Legacy storage changed while reading an object')
    if _identity(path.lstat()) != expected or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Legacy storage changed during import')
    return value


async def _verify_existing(store, uow, context, reference, key, value, owner_type, *, public):
    row = await store._row(uow, context.workspace_uuid, reference)
    if (
        row['public_media'] is not public
        or row['owner_type'] != owner_type
        or row['key'] != key
        or (public and row['public_key'] != key)
        or await store._read(row, HARD_MAX_STORAGE_OBJECT_BYTES) != value
    ):
        raise ValueError('Legacy storage conflicts with existing persistent content')


async def _import_asset(ap, context, uow, key, value, *, verify_only=False):
    store = ap.storage_mgr.content_store
    public = key.startswith('media_cache/')
    if public:
        references = (
            (
                await uow.execute(
                    sa.select(ContentObject.ref).where(
                        ContentObject.workspace_uuid == context.workspace_uuid,
                        ContentObject.public_media.is_(True),
                        ContentObject.public_key == key,
                    )
                )
            )
            .scalars()
            .all()
        )
        for reference in references:
            await _verify_existing(store, uow, context, reference, key, value, 'public_media', public=True)
        if not references:
            if verify_only:
                raise FileNotFoundError('Previously imported public media is missing')
            reference = await store._put(uow, context.workspace_uuid, 'public_media', key, key, value, public_key=key)
            await _verify_existing(store, uow, context, reference, key, value, 'public_media', public=True)
        return

    match = _SCOPED_KEY.fullmatch(key)
    reference = (
        await uow.execute(
            sa.select(ContentAlias.content_ref).where(
                ContentAlias.workspace_uuid == context.workspace_uuid, ContentAlias.key == key
            )
        )
    ).scalar_one_or_none()
    if reference is not None:
        await _verify_existing(store, uow, context, reference, key, value, match['owner_type'], public=False)
        return
    if verify_only:
        raise FileNotFoundError('Previously imported upload is missing')
    # The old key retains only the owner hash; keep it rather than inventing a principal.
    reference = await store._put(uow, context.workspace_uuid, match['owner_type'], match['owner'], key, value)
    insert = sqlite_insert if ap.persistence_mgr.get_db_engine().dialect.name == 'sqlite' else pg_insert
    await uow.execute(
        insert(ContentAlias)
        .values(workspace_uuid=context.workspace_uuid, key=key, content_ref=reference)
        .on_conflict_do_nothing(index_elements=['workspace_uuid', 'key'])
    )
    current = (
        await uow.execute(
            sa.select(ContentAlias.content_ref).where(
                ContentAlias.workspace_uuid == context.workspace_uuid, ContentAlias.key == key
            )
        )
    ).scalar_one()
    if current != reference:
        raise ValueError('Persistent upload changed concurrently with legacy import')
    await _verify_existing(store, uow, context, current, key, value, match['owner_type'], public=False)


async def initialize_storage_migration(ap, *, source_required=False):
    """Import before producers/maintenance start, retaining every source file.

    All old writers must be stopped. Explicit local/S3 configurations are left
    unchanged; selecting persistent imports only the old local provider root.
    """
    if type(source_required) is not bool:
        raise ValueError('storage.migration.require_source must be a boolean')
    if not ap.storage_mgr.persistent_content:
        return {'files': 0, 'bytes': 0}
    contexts = [
        ExecutionContext(
            instance_uuid=b.instance_uuid, workspace_uuid=b.workspace_uuid, placement_generation=b.placement_generation
        )
        for b in await ap.workspace_service.list_active_execution_bindings()
    ]
    migrations = []
    for context in contexts:
        migration = WorkspaceMigration(ap, context, _DOMAIN)
        checkpoint = await migration.checkpoint()
        if checkpoint is None or checkpoint['status'] != 'completed':
            migrations.append((context, migration, checkpoint))
    if contexts and not migrations:
        return {'files': 0, 'bytes': 0}
    recorded_source = getattr(ap, 'legacy_storage_source_exists', None)
    if type(recorded_source) is not bool:
        raise ValueError('Legacy storage source presence was not captured before provider initialization')
    if not recorded_source:
        if source_required or any(checkpoint is not None for _context, _migration, checkpoint in migrations):
            raise FileNotFoundError('The required or pending legacy storage volume is unavailable')
        # A new replica cannot declare an unseen legacy volume completely imported.
        return {'files': 0, 'bytes': 0}
    root = Path(localstorage.LOCAL_STORAGE_PATH).absolute()
    if not contexts:
        inventory, _fingerprint, _source = await run_blocking_atomic(_inventory, root, [], None)
        if not source_required and not inventory:
            return {'files': 0, 'bytes': 0}
        raise ValueError('Legacy storage requires an active Workspace before it can be imported')
    public_workspace = None
    if not ap.workspace_service.policy.multi_workspace_enabled:
        local = await ap.workspace_service.get_local_execution_binding()
        if len(contexts) != 1 or any(
            getattr(local, name) != getattr(contexts[0], name)
            for name in ('instance_uuid', 'workspace_uuid', 'placement_generation')
        ):
            raise ValueError('Legacy public media requires the trusted OSS singleton Workspace')
        public_workspace = local.workspace_uuid
    totals = {'files': 0, 'bytes': 0}
    inventory = None
    for context, migration, _checkpoint in migrations:
        with blocking_work_scope(context.workspace_uuid):
            async with migration as owner:
                if owner.completed:
                    continue
                await owner.renew()
                if inventory is None:
                    inventory, fingerprint, source_root = await run_blocking_atomic(
                        _inventory, root, contexts, public_workspace
                    )
                    if inventory:
                        require_import_runtime(ap)
                if owner.progress and (
                    owner.progress.get('inventory') != fingerprint or owner.progress.get('source_root') != source_root
                ):
                    raise ValueError('Legacy storage source changed; restore it before resuming import')
                if not owner.progress:
                    async with owner.transaction() as (_uow, progress):
                        progress.update(source_root=source_root, inventory=fingerprint, cursor='', files=0, bytes=0)
                original_cursor = owner.progress['cursor']
                for key, identity, workspace in inventory:
                    if workspace != context.workspace_uuid:
                        continue
                    await owner.renew()
                    value = await run_blocking_atomic(_read_source, root, key, identity)
                    if key.startswith('media_cache/'):
                        existing = await ap.storage_mgr.content_store.get_public_media(key)
                        if existing is not None and existing != value:
                            raise ValueError('Legacy media key conflicts with existing public bytes')
                    async with owner.transaction() as (uow, progress):
                        # Recheck committed objects too: neither source nor S3 may silently change on resume.
                        await _import_asset(ap, context, uow, key, value, verify_only=key <= original_cursor)
                        if key > original_cursor:
                            progress.update(
                                cursor=key, files=progress['files'] + 1, bytes=progress['bytes'] + len(value)
                            )
                    del value
                await owner.renew()
                _after_inventory, after, after_root = await run_blocking_atomic(
                    _inventory, root, contexts, public_workspace
                )
                if after != fingerprint or after_root != source_root:
                    raise ValueError('Legacy storage changed before import completed')
                async with owner.transaction(complete=True):
                    pass
                totals['files'] += owner.progress['files']
                totals['bytes'] += owner.progress['bytes']
    return totals
