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
import time
import typing
from datetime import datetime, timezone

import sqlalchemy

from ..utils import constants, platform as platform_utils

if typing.TYPE_CHECKING:
    from ..core import app as core_app


HEARTBEAT_INTERVAL_SECONDS = 24 * 3600


class WorkspaceResourceSnapshot(typing.TypedDict):
    workspace_uuid: str
    bot_count: int
    pipeline_count: int
    knowledge_base_count: int
    plugin_count: int
    mcp_server_count: int
    extension_count: int
    skill_count: int
    agent_count: int
    event_processor_count: int
    plugin_processor_count: int
    event_binding_count: int
    adapters: list[str]
    execution_generation: int


# Agent rows are configuration, not runtime registries, so a Workspace count
# needs one scoped query. The heartbeat runs every five minutes on Cloud; a
# one-hour cache keeps the cost at one bounded query per Workspace per hour
# instead of one per cycle. Unavailable counts stay -1, never a fake zero.
_AGENT_COUNT_CACHE_TTL_SECONDS = 3600
_agent_count_cache: dict[str, tuple[float, dict[str, int]]] = {}


async def _workspace_agent_kind_counts(ap: core_app.Application, workspace_uuid: str) -> dict[str, int]:
    """Count one Workspace's Agents per ``kind``; empty when unavailable."""
    if not workspace_uuid:
        return {}
    now = time.monotonic()
    cached = _agent_count_cache.get(workspace_uuid)
    if cached is not None and cached[0] > now:
        return dict(cached[1])
    counts: dict[str, int] = {}
    try:
        from ..entity.persistence import agent as persistence_agent

        statement = sqlalchemy.select(persistence_agent.Agent.kind, sqlalchemy.func.count()).group_by(
            persistence_agent.Agent.kind
        )
        tenant_uow = getattr(ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(workspace_uuid):
                result = await ap.persistence_mgr.execute_async(statement)
        else:
            result = await ap.persistence_mgr.execute_async(statement)
        for kind, count in result.all():
            counts[str(kind or 'agent')] = int(count or 0)
    except Exception:
        counts = {}
    _agent_count_cache[workspace_uuid] = (now + _AGENT_COUNT_CACHE_TTL_SECONDS, dict(counts))
    return counts


def _bot_processor_counts(bots) -> tuple[int, int]:
    """Count plugin-processor subscriptions and event bindings across bots."""
    processors = 0
    bindings = 0
    for bot in bots:
        entity = getattr(bot, 'bot_entity', bot)
        declared_processors = getattr(entity, 'plugin_processors', None)
        if isinstance(declared_processors, list):
            processors += len(declared_processors)
        declared_bindings = getattr(entity, 'event_bindings', None)
        if isinstance(declared_bindings, list):
            bindings += len(declared_bindings)
    return processors, bindings


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


async def _cloud_workspace_resource_counts(ap: core_app.Application, bindings) -> list[WorkspaceResourceSnapshot]:
    """Summarize already-loaded Cloud registries without per-tenant SQL."""
    persistence_mgr = ap.persistence_mgr
    if getattr(getattr(persistence_mgr, 'mode', None), 'value', None) != 'cloud_runtime':
        return []

    counts: dict[str, WorkspaceResourceSnapshot] = {
        binding.workspace_uuid: {
            'workspace_uuid': binding.workspace_uuid,
            'bot_count': 0,
            'pipeline_count': 0,
            'knowledge_base_count': 0,
            'plugin_count': 0,
            'mcp_server_count': 0,
            'extension_count': 0,
            'skill_count': 0,
            'agent_count': -1,
            'event_processor_count': -1,
            'plugin_processor_count': 0,
            'event_binding_count': 0,
            'adapters': [],
            'execution_generation': binding.placement_generation,
        }
        for binding in bindings
    }

    adapter_sets: dict[str, set[str]] = {workspace_uuid: set() for workspace_uuid in counts}
    for key, bot in getattr(ap.platform_mgr, '_bots_by_key', {}).items():
        if len(key) >= 2 and key[1] in counts:
            counts[key[1]]['bot_count'] += 1
            processors, bindings = _bot_processor_counts([bot])
            counts[key[1]]['plugin_processor_count'] += processors
            counts[key[1]]['event_binding_count'] += bindings
            adapter = getattr(bot, 'adapter', None)
            if adapter is not None and getattr(bot, 'enable', False):
                adapter_sets[key[1]].add(adapter.__class__.__name__)
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
    for key, skills in getattr(ap.skill_mgr, '_skills_by_scope', {}).items():
        if len(key) >= 2 and key[1] in counts:
            counts[key[1]]['skill_count'] += len(skills)

    for workspace_uuid, resource in counts.items():
        resource['extension_count'] = resource['plugin_count'] + resource['mcp_server_count']
        resource['adapters'] = sorted(adapter_sets[workspace_uuid])
        agent_counts = await _workspace_agent_kind_counts(ap, workspace_uuid)
        if agent_counts:
            resource['agent_count'] = int(agent_counts.get('agent', 0))
            resource['event_processor_count'] = int(agent_counts.get('event_processor', 0))
    return list(counts.values())


async def build_heartbeat_payload(
    ap: core_app.Application,
    *,
    workspace_uuid: str,
    workspace_create_ts: int = 0,
    workspace_resource: WorkspaceResourceSnapshot | None = None,
) -> dict:
    """Collect one anonymous Workspace profile snapshot."""
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
            processors, bindings = _bot_processor_counts(platform_mgr.bots)
            features['plugin_processor_count'] = processors
            features['event_binding_count'] = bindings
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

    # Scoped Cloud counts are already available; never issue tenantless RPCs.
    try:
        plugin_connector = getattr(ap, 'plugin_connector', None)
        if workspace_resource is None and plugin_connector is not None:
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

    # Agent processors: configuration rows, so one scoped count per Workspace.
    # The Cloud snapshot supplies these already and overrides below.
    if workspace_resource is None:
        agent_counts = await _workspace_agent_kind_counts(ap, workspace_uuid)
        features['agent_count'] = int(agent_counts.get('agent', 0)) if agent_counts else -1
        features['event_processor_count'] = int(agent_counts.get('event_processor', 0)) if agent_counts else -1

    if workspace_resource is not None:
        features.update({key: value for key, value in workspace_resource.items() if key != 'workspace_uuid'})

    return {
        'event_type': 'instance_heartbeat',
        'query_id': '',
        'version': constants.semantic_version,
        'instance_id': constants.instance_id,
        'workspace_uuid': workspace_uuid,
        'workspace_create_ts': workspace_create_ts,
        'instance_create_ts': constants.instance_create_ts,
        'edition': constants.edition,
        'features': features,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


def _workspace_created_timestamp(created_at: datetime | None) -> int:
    if created_at is None:
        return 0
    if created_at.tzinfo is None:
        # SQLAlchemy may return persisted UTC values without tzinfo. Never
        # reinterpret them in the host's local timezone.
        created_at = created_at.replace(tzinfo=timezone.utc)
    return int(created_at.timestamp())


async def build_heartbeat_payloads(ap: core_app.Application) -> list[dict]:
    """Build one heartbeat per active Workspace."""
    bindings = await ap.workspace_service.list_active_execution_bindings()
    workspace_uuids = sorted({binding.workspace_uuid for binding in bindings})
    workspace_create_ts = {
        binding.workspace_uuid: _workspace_created_timestamp(getattr(binding, 'workspace_created_at', None))
        for binding in bindings
    }
    resources = {
        resource['workspace_uuid']: resource for resource in await _cloud_workspace_resource_counts(ap, bindings)
    }
    return [
        await build_heartbeat_payload(
            ap,
            workspace_uuid=workspace_uuid,
            workspace_create_ts=workspace_create_ts.get(workspace_uuid, 0),
            workspace_resource=resources.get(workspace_uuid),
        )
        for workspace_uuid in workspace_uuids
    ]


async def heartbeat_loop(ap: core_app.Application) -> None:
    """Send one heartbeat shortly after startup, then daily."""
    # Small delay so managers (platform, skills, plugins) finish loading first
    await asyncio.sleep(30)
    while True:
        try:
            for payload in await build_heartbeat_payloads(ap):
                # Heartbeats are a daily bounded batch, not best-effort query events.
                # Await each send so the TelemetryManager's 8-task queue cannot drop
                # Workspaces after the first batch.
                await ap.telemetry.send(payload)
        except Exception as e:
            try:
                ap.logger.debug(f'Telemetry heartbeat failed: {e}')
            except Exception:
                pass
        # Cloud dashboards need fresh scoped snapshots, including Workspaces
        # discovered after startup. A transient startup/projection failure must
        # not suppress synchronization for an entire day.
        cloud_runtime = getattr(getattr(ap.persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime'
        await asyncio.sleep(300 if cloud_runtime else HEARTBEAT_INTERVAL_SECONDS)
