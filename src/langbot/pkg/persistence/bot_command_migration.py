"""Migration of legacy global command configuration from config.yaml into bot entities."""

from __future__ import annotations

import json
import typing

import sqlalchemy as sa

if typing.TYPE_CHECKING:
    from ...core import app

MIGRATION_FLAG_KEY = 'command_config_migrated_to_bots'


def legacy_command_updates(cfg_data: typing.Any) -> dict | None:
    """Bot ``command_settings`` keys equivalent to the legacy ``command`` section, or None if absent."""
    if not isinstance(cfg_data, dict) or not isinstance(cfg_data.get('command'), dict):
        return None
    command_cfg = cfg_data['command']
    updates: dict = {}
    if 'enable' in command_cfg:
        updates['enabled'] = bool(command_cfg.get('enable', True))
    if 'prefix' in command_cfg:
        raw_prefix = command_cfg.get('prefix')
        if isinstance(raw_prefix, list):
            clean = [str(p) for p in raw_prefix if isinstance(p, (str, int)) and str(p).strip()]
            updates['prefixes'] = clean if clean else ['/']
        elif isinstance(raw_prefix, str) and raw_prefix.strip():
            updates['prefixes'] = [raw_prefix.strip()]
        else:
            updates['prefixes'] = ['/']
    return updates or None


async def migrate_global_command_config_for_release(ap: app.Application, engine: typing.Any) -> None:
    """Cloud release-migration counterpart of :func:`migrate_global_command_config`.

    Multi-workspace runtimes skip the startup migration, so the operator-only
    release job carries the instance-wide ``command`` section into the
    ``command_settings`` of every bot in every workspace, once. The legacy keys
    stay in config.yaml (the runtime ignores them); the job must not rewrite
    a shared configuration file.
    """
    from ..entity.persistence.metadata import Metadata, WorkspaceMetadata
    from ..entity.persistence.bot import Bot
    from .message_upgrade_report import REPORT_PREFIX, report_value

    updates = legacy_command_updates(getattr(getattr(ap, 'instance_config', None), 'data', None))
    report_key = REPORT_PREFIX + 'commands'
    async with engine.begin() as conn:
        done = await conn.execute(sa.select(Metadata.value).where(Metadata.key == MIGRATION_FLAG_KEY))
        if done.scalar_one_or_none() is not None:
            return
        migrated = 0
        workspaces: set[str] = set()
        if updates:
            rows = await conn.execute(sa.select(Bot.workspace_uuid, Bot.uuid, Bot.command_settings))
            for workspace, bot_uuid, settings in rows.all():
                if isinstance(settings, str):
                    settings = json.loads(settings)
                await conn.execute(
                    Bot.__table__.update()
                    .where(Bot.workspace_uuid == workspace, Bot.uuid == bot_uuid)
                    .values(command_settings={**(settings or {}), **updates})
                )
                workspaces.add(workspace)
                migrated += 1
            reported = set(
                (
                    await conn.execute(
                        sa.select(WorkspaceMetadata.workspace_uuid).where(WorkspaceMetadata.key == report_key)
                    )
                ).scalars()
            )
            value = report_value({'original_prefixes': updates.get('prefixes', [])})
            for workspace in sorted(workspaces - reported):
                await conn.execute(
                    sa.insert(WorkspaceMetadata).values(workspace_uuid=workspace, key=report_key, value=value)
                )
        await conn.execute(sa.insert(Metadata).values(key=MIGRATION_FLAG_KEY, value='true'))
    logger = getattr(ap, 'logger', None)
    if logger is not None:
        logger.info(
            f'Release migration applied legacy command config {updates or {}} to {migrated} bots '
            f'in {len(workspaces)} workspaces.'
        )


async def migrate_global_command_config(ap: app.Application) -> None:
    """Migrate legacy command.enable and command.prefix from instance_config to bots.

    Runs during application startup after instance_config and persistence_mgr are initialized.
    Guaranteed to run at most once via database metadata flag.
    """
    persistence = getattr(ap, 'persistence_mgr', None)
    if persistence is None:
        return

    from .mgr import PersistenceMode

    if getattr(persistence, 'mode', None) in {PersistenceMode.CLOUD_RUNTIME, PersistenceMode.RELEASE_MIGRATION}:
        return

    from ..entity.persistence.metadata import Metadata, WorkspaceMetadata
    from ..entity.persistence.bot import Bot
    from .message_upgrade_report import REPORT_PREFIX, report_value

    # Check if migration has already been executed
    result = await persistence.execute_async(sa.select(Metadata.value).where(Metadata.key == MIGRATION_FLAG_KEY))
    if result.scalar_one_or_none() is not None:
        return

    instance_cfg = getattr(ap, 'instance_config', None)
    cfg_data = getattr(instance_cfg, 'data', None)
    updates = legacy_command_updates(cfg_data)
    has_legacy_config = updates is not None
    old_enabled = (updates or {}).get('enabled', True)
    old_prefixes = (updates or {}).get('prefixes', ['/'])

    # Migrate values into all existing bots if legacy config exists
    if has_legacy_config:
        workspace = (await ap.workspace_service.get_singleton_workspace()).uuid
        async with persistence.tenant_uow(workspace) as uow:
            bots = await uow.execute(sa.select(Bot.uuid, Bot.command_settings).where(Bot.workspace_uuid == workspace))
            for bot_uuid, settings in bots.all():
                await uow.execute(
                    Bot.__table__.update()
                    .where(Bot.workspace_uuid == workspace, Bot.uuid == bot_uuid)
                    .values(command_settings={**(settings or {}), **updates})
                )
            await uow.execute(
                sa.insert(WorkspaceMetadata).values(
                    workspace_uuid=workspace,
                    key=REPORT_PREFIX + 'commands',
                    value=report_value({'original_prefixes': updates.get('prefixes', [])}),
                )
            )
            await uow.execute(sa.insert(Metadata).values(key=MIGRATION_FLAG_KEY, value='true'))

    # Mark migration complete in database metadata so it runs only once
    else:
        await persistence.execute_async(sa.insert(Metadata).values(key=MIGRATION_FLAG_KEY, value='true'))

    # Remove legacy keys from data/config.yaml and dump config
    if instance_cfg is not None and isinstance(cfg_data, dict) and 'command' in cfg_data:
        command_cfg = cfg_data['command']
        if isinstance(command_cfg, dict):
            removed = False
            if 'enable' in command_cfg:
                command_cfg.pop('enable', None)
                removed = True
            if 'prefix' in command_cfg:
                command_cfg.pop('prefix', None)
                removed = True
            if removed and hasattr(instance_cfg, 'dump_config'):
                await instance_cfg.dump_config()

    logger = getattr(ap, 'logger', None)
    if logger is not None:
        logger.info(
            f'Migrated legacy global command config (enabled={old_enabled}, prefixes={old_prefixes}) '
            f'to bot entities and removed legacy keys from data/config.yaml.'
        )
