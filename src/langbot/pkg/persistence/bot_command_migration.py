"""Migration of legacy global command configuration from config.yaml into bot entities."""

from __future__ import annotations

import typing
import sqlalchemy as sa

if typing.TYPE_CHECKING:
    from ...core import app

MIGRATION_FLAG_KEY = 'command_config_migrated_to_bots'


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

    from ..entity.persistence.metadata import Metadata
    from ..entity.persistence.bot import Bot

    # Check if migration has already been executed
    result = await persistence.execute_async(sa.select(Metadata.value).where(Metadata.key == MIGRATION_FLAG_KEY))
    if result.scalar_one_or_none() is not None:
        return

    # Extract legacy global config from instance_config if present
    old_enabled = True
    old_prefixes = ['/']
    has_legacy_config = False

    instance_cfg = getattr(ap, 'instance_config', None)
    cfg_data = getattr(instance_cfg, 'data', None)
    if isinstance(cfg_data, dict) and 'command' in cfg_data:
        command_cfg = cfg_data['command']
        if isinstance(command_cfg, dict):
            if 'enable' in command_cfg:
                old_enabled = bool(command_cfg.get('enable', True))
                has_legacy_config = True
            if 'prefix' in command_cfg:
                raw_prefix = command_cfg.get('prefix')
                if isinstance(raw_prefix, list):
                    clean = [str(p) for p in raw_prefix if isinstance(p, (str, int)) and str(p).strip()]
                    old_prefixes = clean if clean else ['/']
                elif isinstance(raw_prefix, str) and raw_prefix.strip():
                    old_prefixes = [raw_prefix.strip()]
                else:
                    old_prefixes = ['/']
                has_legacy_config = True

    # Migrate values into all existing bots if legacy config exists
    target_settings = {
        'enabled': old_enabled,
        'prefixes': old_prefixes,
        'processors': [],
    }

    if has_legacy_config:
        await persistence.execute_async(Bot.__table__.update().values(command_settings=target_settings))

    # Mark migration complete in database metadata so it runs only once
    await persistence.execute_async(
        sa.insert(Metadata).values(
            key=MIGRATION_FLAG_KEY,
            value='true',
        )
    )

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
