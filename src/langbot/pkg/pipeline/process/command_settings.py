from __future__ import annotations

import typing
from ...pipeline.pool import get_query_execution_context

if typing.TYPE_CHECKING:
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


_CACHE_KEY = '_bot_command_settings'


async def get_bot_command_settings(ap: typing.Any, query: pipeline_query.Query) -> tuple[bool, list[str]]:
    """Return the bot command switch and prefixes, cached on the query for repeated scheduler checks."""
    variables = getattr(query, 'variables', None)
    if isinstance(variables, dict):
        cached = variables.get(_CACHE_KEY)
        if isinstance(cached, tuple) and len(cached) == 2:
            return cached[0], list(cached[1])
    result = await _resolve_bot_command_settings(ap, query)
    if isinstance(variables, dict):
        variables[_CACHE_KEY] = (result[0], tuple(result[1]))
    return result


async def _resolve_bot_command_settings(ap: typing.Any, query: pipeline_query.Query) -> tuple[bool, list[str]]:
    """Retrieve command enabled status and prefixes from in-memory RuntimeBot without querying the database."""
    default_enabled = True
    default_prefixes = ['/']

    if not getattr(query, 'bot_uuid', None):
        return default_enabled, default_prefixes

    platform_mgr = getattr(ap, 'platform_mgr', None)
    if platform_mgr and hasattr(platform_mgr, 'get_bot_by_uuid'):
        try:
            try:
                ctx = get_query_execution_context(query)
            except Exception:
                from ...api.http.context import ExecutionContext

                ctx = ExecutionContext(
                    instance_uuid=getattr(query, 'instance_uuid', 'default') or 'default',
                    workspace_uuid=getattr(query, 'workspace_uuid', 'default') or 'default',
                    placement_generation=getattr(query, 'placement_generation', 1) or 1,
                    bot_uuid=query.bot_uuid,
                )
            runtime_bot = await platform_mgr.get_bot_by_uuid(ctx, query.bot_uuid)
            if runtime_bot is not None:
                bot_entity = getattr(runtime_bot, 'bot_entity', runtime_bot)
                settings = getattr(bot_entity, 'command_settings', None)
                if isinstance(settings, dict):
                    enabled = bool(settings.get('enabled', True))
                    prefixes = settings.get('prefixes', ['/'])
                    if isinstance(prefixes, list) and prefixes:
                        clean = [str(p) for p in prefixes if isinstance(p, str) and p.strip()]
                        return enabled, clean if clean else ['/']
                    return enabled, ['/']
        except Exception as exc:
            logger = getattr(ap, 'logger', None)
            if logger is not None:
                logger.warning(f'Failed to get bot command settings from platform_mgr for {query.bot_uuid}: {exc}')

    # Fallback to bot_service if platform_mgr is absent (e.g. in isolated legacy tests)
    bot_service = getattr(ap, 'bot_service', None)
    if bot_service and hasattr(bot_service, 'get_bot'):
        try:
            bot = await bot_service.get_bot(
                getattr(query, 'workspace_uuid', ''),
                query.bot_uuid,
                include_secret=False,
            )
            if bot and 'command_settings' in bot and isinstance(bot['command_settings'], dict):
                enabled = bool(bot['command_settings'].get('enabled', True))
                prefixes = bot['command_settings'].get('prefixes', ['/'])
                if isinstance(prefixes, list) and prefixes:
                    clean = [str(p) for p in prefixes if isinstance(p, str) and p.strip()]
                    return enabled, clean if clean else ['/']
                return enabled, ['/']
        except Exception:
            pass

    return default_enabled, default_prefixes
