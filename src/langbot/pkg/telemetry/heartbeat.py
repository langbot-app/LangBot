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


async def _count(
    ap: core_app.Application,
    table,
    *,
    cloud_counter: typing.Callable[[], int] | None = None,
) -> int:
    """Count rows in a persistence table; -1 when unavailable."""
    try:
        persistence_mgr = ap.persistence_mgr
        cloud_runtime = getattr(getattr(persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime'
        if cloud_runtime:
            # The Cloud runtime role deliberately cannot bypass RLS. Counting
            # every tenant by opening one UoW per Workspace turns a best-effort
            # daily heartbeat into thousands of serial SQL statements. The
            # already-loaded runtime registries are authoritative for this
            # process and provide an O(1), connection-free operational count.
            if cloud_counter is None:
                return -1
            return max(int(cloud_counter()), 0)
        result = await ap.persistence_mgr.execute_async(sqlalchemy.select(sqlalchemy.func.count()).select_from(table))
        return int(result.scalar() or 0)
    except Exception:
        return -1


async def _cloud_workspace_resource_counts(ap: core_app.Application) -> list[dict]:
    """Summarize already-loaded Cloud registries without per-tenant SQL."""
    persistence_mgr = ap.persistence_mgr
    if getattr(getattr(persistence_mgr, 'mode', None), 'value', None) != 'cloud_runtime':
        return []

    bindings = await ap.workspace_service.list_active_execution_bindings()
    counts = {
        binding.workspace_uuid: {
            'workspace_uuid': binding.workspace_uuid,
            'bot_count': 0,
            'pipeline_count': 0,
            'knowledge_base_count': 0,
            'plugin_count': 0,
            'mcp_server_count': 0,
            'extension_count': 0,
        }
        for binding in bindings
    }

    for key in getattr(ap.platform_mgr, '_bots_by_key', {}):
        if len(key) >= 2 and key[1] in counts:
            counts[key[1]]['bot_count'] += 1
    for key in getattr(ap.pipeline_mgr, '_pipelines_by_key', {}):
        if len(key) >= 2 and key[1] in counts:
            counts[key[1]]['pipeline_count'] += 1
    for key in getattr(ap.rag_mgr, 'knowledge_bases', {}):
        if len(key) >= 1 and key[0] in counts:
            counts[key[0]]['knowledge_base_count'] += 1
    for key in getattr(ap.tool_mgr.mcp_tool_loader, '_sessions', {}):
        if len(key) >= 2 and key[1] in counts:
            counts[key[1]]['mcp_server_count'] += 1
    for workspace_uuid, installations in getattr(ap.plugin_connector, '_workspace_installations', {}).items():
        if workspace_uuid in counts:
            counts[workspace_uuid]['plugin_count'] = len(installations)

    for resource in counts.values():
        resource['extension_count'] = resource['plugin_count'] + resource['mcp_server_count']
    return list(counts.values())


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
    features['pipeline_count'] = await _count(
        ap,
        persistence_pipeline.LegacyPipeline,
        cloud_counter=lambda: len(ap.pipeline_mgr._pipelines_by_key),
    )
    features['mcp_server_count'] = await _count(
        ap,
        persistence_mcp.MCPServer,
        cloud_counter=lambda: len(ap.tool_mgr.mcp_tool_loader._sessions),
    )
    features['knowledge_base_count'] = await _count(
        ap,
        persistence_rag.KnowledgeBase,
        cloud_counter=lambda: len(ap.rag_mgr.knowledge_bases),
    )
    if 'bot_count' not in features:
        features['bot_count'] = await _count(
            ap,
            persistence_bot.Bot,
            cloud_counter=lambda: len(ap.platform_mgr._bots_by_key),
        )

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

    workspace_resources = await _cloud_workspace_resource_counts(ap)
    if workspace_resources:
        features['workspace_resources'] = workspace_resources

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
