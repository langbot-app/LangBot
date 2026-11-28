"""Import stopped legacy Skill stores before database-backed producers start."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from langbot_plugin.skill_store import SkillStore, skill_namespace

from ..api.http.context import ExecutionContext
from ..persistence.legacy_migration import WorkspaceMigration, require_import_runtime
from ..utils.bounded_executor import run_blocking_atomic
from .database_repository import MAX_PUBLICATION_BYTES, DatabaseSkillRepository


_DOMAIN = 'skills-filesystem-v1'


def _source_layout(root):
    try:
        mode = os.stat(root, follow_symlinks=False).st_mode
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(mode):
        raise ValueError('Legacy Skill root must be an accessible directory')
    entries = list(os.scandir(root))
    if any(entry.name.lower() == 'skill.md' for entry in entries):
        raise ValueError('Legacy Skill source must be a store root, not a package directory')
    namespaces = set()
    for entry in entries:
        if entry.name != 'tenants':
            continue
        if not entry.is_dir(follow_symlinks=False):
            raise ValueError('Legacy Skill tenant root must be a directory')
        for child in os.scandir(entry.path):
            if not child.is_dir(follow_symlinks=False):
                raise ValueError('Legacy Skill tenant namespace must be a directory')
            namespaces.add(child.name)
    flat = any(entry.name not in {'tenants', '.database-cache'} for entry in entries)
    if flat and namespaces:
        raise ValueError('Legacy Skill root mixes unscoped and tenant stores; select the original source explicitly')
    return namespaces, flat


def _fingerprint(inventory):
    value = {
        'skills': [DatabaseSkillRepository._migration_skill(skill) for skill in inventory['skills']],
        'versions': inventory['versions'],
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    ).hexdigest()


def _export_verified(store, version):
    publication = store.export_skill_publication(version['name'], version['revision'], max_bytes=MAX_PUBLICATION_BYTES)
    if len(publication['file_bytes']) > MAX_PUBLICATION_BYTES:
        raise ValueError('Legacy Skill publication exceeds the 64 MiB migration limit')
    if (publication['skill']['name'], publication['skill']['revision']) != (version['name'], version['revision']):
        raise ValueError('Legacy Skill publication changed its identity during export')
    SkillStore.read_publication_resource(
        publication['skill'],
        publication['manifest'],
        publication['file_bytes'],
        'SKILL.md',
        expected_revision=version['revision'],
    )
    return publication


async def _migrate_store(ap, context, store, owner):
    database = ap.skill_repository._database
    source = str(Path(store.root).resolve())
    async with owner.transaction() as (_uow, progress):
        previous = progress.get('source')
        if previous is not None and previous != source:
            raise ValueError('Legacy Skill migration source changed; restore the recorded source before retrying')
        progress['source'] = source
    if not callable(getattr(store, 'publication_inventory', None)):
        raise ValueError('Skill migration requires a compatible Core and SDK')
    await owner.renew()
    inventory = await run_blocking_atomic(store.publication_inventory)
    if inventory['versions']:
        require_import_runtime(ap)
    fingerprint = _fingerprint(inventory)
    async with owner.transaction() as (_uow, progress):
        if progress.get('fingerprint', fingerprint) != fingerprint:
            raise ValueError('Legacy Skill source changed after migration began; keep old writers stopped')
        progress.update(fingerprint=fingerprint, versions=len(inventory['versions']), verified_versions=0)
    # Recheck committed versions on retry: their target blobs may have become unavailable.
    for index, version in enumerate(inventory['versions']):
        await owner.renew()
        publication = await run_blocking_atomic(_export_verified, store, version)
        async with owner.transaction() as (uow, progress):
            await database.import_retained_publication(context, publication, uow)
            progress['verified_versions'] = index + 1
    await owner.renew()
    if await run_blocking_atomic(lambda: _fingerprint(store.publication_inventory())) != fingerprint:
        raise ValueError('Legacy Skill source changed during migration; current pointers were not switched')
    async with owner.transaction(complete=True) as (uow, progress):
        await database.publish_migrated_registry(context, inventory['skills'], uow)
        progress['registrations'] = len(inventory['skills'])
    ap.logger.info(
        'Migrated %s Skill versions and %s registrations for Workspace %s',
        len(inventory['versions']),
        len(inventory['skills']),
        context.workspace_uuid,
    )


async def initialize_skill_migration(ap, *, source_required: bool = False):
    """Discover only authenticated tenant namespaces; never infer unknown owners.

    A completed database checkpoint makes the old root unnecessary. An absent
    unrecorded root is indistinguishable from a fresh replica unless the operator
    explicitly requires the source; pending imports always require their volume.
    """
    repository = ap.skill_repository
    if not repository.database_backed:
        return
    cloud = bool(getattr(getattr(ap, 'deployment', None), 'multi_workspace_enabled', False))
    bindings = (
        await ap.workspace_service.list_active_execution_bindings()
        if cloud
        else [await ap.workspace_service.get_local_execution_binding()]
    )
    contexts = [
        ExecutionContext(
            instance_uuid=binding.instance_uuid,
            workspace_uuid=binding.workspace_uuid,
            placement_generation=binding.placement_generation,
        )
        for binding in bindings
    ]
    owners = [WorkspaceMigration(ap, context, _DOMAIN) for context in contexts]
    checkpoints = [await owner.checkpoint() for owner in owners]
    pending = [
        (context, owner, checkpoint)
        for context, owner, checkpoint in zip(contexts, owners, checkpoints, strict=True)
        if checkpoint is None or checkpoint['status'] != 'completed'
    ]
    if contexts and not pending:
        return
    root = repository._skills_root()
    layout = await run_blocking_atomic(_source_layout, root)
    if layout is None:
        if source_required or any(checkpoint and checkpoint['progress'].get('source') for _, _, checkpoint in pending):
            raise ValueError('Required legacy Skill source is unavailable; mount its original volume before starting')
        return
    namespaces, flat = layout
    known = {skill_namespace(context.instance_uuid, context.workspace_uuid): context for context in contexts}
    if (
        not namespaces
        and not flat
        and not source_required
        and not any(checkpoint and checkpoint['progress'].get('source') for _, _, checkpoint in pending)
    ):
        return
    if namespaces - known.keys():
        raise ValueError('Legacy Skill source contains an unknown or inactive Workspace namespace')
    if flat and (cloud or len(contexts) != 1):
        raise ValueError('Unscoped legacy Skill data requires one verified OSS-local Workspace')
    if source_required and not contexts:
        raise ValueError('Legacy Skill source has no active, verifiable Workspace owner')
    for context, owner, checkpoint in pending:
        namespace = skill_namespace(context.instance_uuid, context.workspace_uuid)
        source = root if flat or (not namespaces and not cloud) else os.path.join(root, 'tenants', namespace)
        if namespace not in namespaces and source != root:
            if checkpoint and checkpoint['progress'].get('source'):
                raise ValueError('Pending legacy Skill source is unavailable; restore its original volume')
            continue
        async with owner:
            if owner.completed:
                continue
            await _migrate_store(ap, context, SkillStore(source), owner)
