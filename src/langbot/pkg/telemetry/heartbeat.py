"""Instance heartbeat telemetry.

Sends a periodic (startup + daily) anonymous snapshot of the instance's
configuration profile so feature *adoption* can be measured separately from
feature *usage* (which is covered by per-query telemetry).

The snapshot contains only configuration categories and object counts —
never names of user resources (except adapter type names, which are LangBot
adapter identifiers, not account info), never message content, never
credentials.
"""

from __future__ import annotations

import asyncio
import typing
from datetime import datetime, timezone

import sqlalchemy

from ..utils import constants, platform as platform_utils

if typing.TYPE_CHECKING:
    from ..core import app as core_app


HEARTBEAT_INTERVAL_SECONDS = 24 * 3600


async def _count(ap: core_app.Application, table) -> int:
    """Count rows in a persistence table; -1 when unavailable."""
    try:
        persistence_mgr = ap.persistence_mgr
        cloud_runtime = getattr(getattr(persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime'
        if cloud_runtime:
            tenant_uow = getattr(persistence_mgr, 'tenant_uow', None)
            if not callable(tenant_uow):
                return -1
            total = 0
            for binding in await ap.workspace_service.list_active_execution_bindings():
                async with tenant_uow(binding.workspace_uuid):
                    result = await persistence_mgr.execute_async(
                        sqlalchemy.select(sqlalchemy.func.count()).select_from(table)
                    )
                    total += int(result.scalar() or 0)
            return total
        result = await ap.persistence_mgr.execute_async(sqlalchemy.select(sqlalchemy.func.count()).select_from(table))
        return int(result.scalar() or 0)
    except Exception:
        return -1


async def build_heartbeat_payload(ap: core_app.Application) -> dict:
    """Collect the anonymous instance profile snapshot."""
    from ..entity.persistence import bot as persistence_bot
    from ..entity.persistence import mcp as persistence_mcp
    from ..entity.persistence import pipeline as persistence_pipeline
    from ..entity.persistence import rag as persistence_rag

    config = ap.instance_config.data if ap.instance_config else {}

    features: dict = {
        'deploy_platform': platform_utils.get_platform(),
        'database': config.get('database', {}).get('use', 'sqlite'),
        'vdb': config.get('vdb', {}).get('use', 'chroma'),
    }

    # Box / sandbox profile
    try:
        box_service = getattr(ap, 'box_service', None)
        if box_service is not None:
            box_info: dict = {
                'enabled': bool(box_service.enabled),
                'available': bool(box_service.available),
            }
            box_cfg = config.get('box', {})
            box_info['backend'] = box_cfg.get('backend', 'local')
            try:
                box_info['shares_fs'] = bool(box_service.shares_filesystem_with_box)
            except Exception:
                pass
            features['box'] = box_info
    except Exception:
        pass

    # Bots / adapters (adapter type names only)
    try:
        platform_mgr = getattr(ap, 'platform_mgr', None)
        if platform_mgr is not None and getattr(platform_mgr, 'bots', None) is not None:
            enabled_bots = [bot for bot in platform_mgr.bots if getattr(bot, 'enable', False)]
            features['bot_count'] = len(platform_mgr.bots)
            adapters = sorted({bot.adapter.__class__.__name__ for bot in enabled_bots if getattr(bot, 'adapter', None)})
            features['adapters'] = adapters
    except Exception:
        pass

    # Resource counts
    features['pipeline_count'] = await _count(ap, persistence_pipeline.LegacyPipeline)
    features['mcp_server_count'] = await _count(ap, persistence_mcp.MCPServer)
    features['knowledge_base_count'] = await _count(ap, persistence_rag.KnowledgeBase)
    if 'bot_count' not in features:
        features['bot_count'] = await _count(ap, persistence_bot.Bot)

    # Plugin count (from plugin runtime)
    try:
        plugin_connector = getattr(ap, 'plugin_connector', None)
        if plugin_connector is not None:
            plugins = await plugin_connector.list_plugins()
            features['plugin_count'] = len(plugins)
    except Exception:
        features['plugin_count'] = -1

    # Skill count (from Box runtime via skill manager)
    try:
        skill_mgr = getattr(ap, 'skill_mgr', None)
        if skill_mgr is not None:
            features['skill_count'] = skill_mgr.total_cached_skill_count()
    except Exception:
        pass

    return {
        'event_type': 'instance_heartbeat',
        'query_id': '',
        'version': constants.semantic_version,
        'instance_id': constants.instance_id,
        'instance_create_ts': constants.instance_create_ts,
        'edition': constants.edition,
        'features': features,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


async def heartbeat_loop(ap: core_app.Application) -> None:
    """Send one heartbeat shortly after startup, then daily."""
    # Small delay so managers (platform, skills, plugins) finish loading first
    await asyncio.sleep(30)
    while True:
        try:
            payload = await build_heartbeat_payload(ap)
            await ap.telemetry.start_send_task(payload)
        except Exception as e:
            try:
                ap.logger.debug(f'Telemetry heartbeat failed: {e}')
            except Exception:
                pass
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
