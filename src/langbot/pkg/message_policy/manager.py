"""Resolves and caches the message policy runtime of each bot route."""

from __future__ import annotations

import asyncio
import json
import typing

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from ..utils import constants
from . import runtime as policy_runtime
from . import schema

if typing.TYPE_CHECKING:
    from ..core import app

ROUTE_VARIABLE = '_message_route_id'
"""Query variable naming the bot route (event binding id) a message matched."""

_QUERY_ATTRIBUTE = '_message_policy'
_DEFAULT_ROUTE = ''


def get_query_policy(query: pipeline_query.Query) -> policy_runtime.MessagePolicyRuntime | None:
    """Return the policy runtime already bound to a query, if any."""
    return getattr(query, _QUERY_ATTRIBUTE, None)


def _bindings(raw: typing.Any) -> list[dict[str, typing.Any]]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    return [binding for binding in raw if isinstance(binding, dict)]


def select_route(
    event_bindings: typing.Any,
    *,
    route_id: str | None = None,
    pipeline_uuid: str | None = None,
) -> dict[str, typing.Any] | None:
    """Pick the route whose policy override applies to a message.

    The route the message actually matched wins. A message that reaches a
    Messaging processor without one (web page widget, form callbacks) uses the
    bot's first enabled route to that processor, in routing precedence.
    """
    bindings = _bindings(event_bindings)
    if route_id:
        for binding in bindings:
            if str(binding.get('id') or '') == route_id:
                return binding
    if not pipeline_uuid:
        return None
    matched: list[tuple[int, int, dict[str, typing.Any]]] = []
    for index, binding in enumerate(bindings):
        if not binding.get('enabled', True) or binding.get('target_type') != 'pipeline':
            continue
        if str(binding.get('target_uuid') or '') != pipeline_uuid:
            continue
        try:
            priority = int(binding.get('priority') or 0)
            order = int(binding.get('order', index))
        except (TypeError, ValueError):
            priority, order = 0, index
        matched.append((priority, -order, binding))
    if not matched:
        return None
    matched.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return matched[0][2]


class _BotCache:
    """Compiled runtimes of one bot, valid for one loaded bot entity."""

    def __init__(self, bot_entity: typing.Any):
        self.bot_entity = bot_entity
        self.runtimes: dict[str, policy_runtime.MessagePolicyRuntime] = {}


class MessagePolicyManager:
    """Compiles policies on demand and caches them per bot and route."""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self._bots: dict[tuple[str, str], _BotCache] = {}
        self._neutral: policy_runtime.MessagePolicyRuntime | None = None
        self._rate_limiter: typing.Any = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ lookup

    def _find_bot_entity(self, execution_context: typing.Any, bot_uuid: str | None) -> typing.Any:
        """Return the loaded entity of a real bot, or None for the debug chat and unknown bots."""
        if not bot_uuid or bot_uuid == constants.WEBSOCKET_PROXY_BOT_UUID:
            return None
        platform_mgr = getattr(self.ap, 'platform_mgr', None)
        find = getattr(platform_mgr, 'find_runtime_bot', None)
        if not callable(find):
            return None
        runtime_bot = find(execution_context, bot_uuid)
        return getattr(runtime_bot, 'bot_entity', None)

    def effective_policy(
        self,
        execution_context: typing.Any,
        bot_uuid: str | None,
        *,
        route_id: str | None = None,
        pipeline_uuid: str | None = None,
    ) -> dict[str, typing.Any]:
        """Return the complete policy for a message without compiling a runtime."""
        bot_entity = self._find_bot_entity(execution_context, bot_uuid)
        if bot_entity is None:
            return schema.neutral_policy()
        route = select_route(
            getattr(bot_entity, 'event_bindings', None), route_id=route_id, pipeline_uuid=pipeline_uuid
        )
        return schema.resolve_policy(
            getattr(bot_entity, 'message_policy', None),
            route.get('policy') if route else None,
        )

    # ----------------------------------------------------------------- runtime

    async def _shared_rate_limiter(self) -> typing.Any:
        # One limiter for the whole application: its counters are keyed by
        # workspace, bot, processor and session, so they survive policy edits.
        if self._rate_limiter is None:
            self._rate_limiter = await policy_runtime.create_rate_limiter(self.ap)
        return self._rate_limiter

    async def compile(
        self,
        policy: typing.Any,
        *,
        bot_uuid: str = '',
        route_id: str | None = None,
    ) -> policy_runtime.MessagePolicyRuntime:
        """Build an uncached runtime for a policy."""
        compiled = policy_runtime.MessagePolicyRuntime(
            self.ap,
            policy,
            bot_uuid=bot_uuid,
            route_id=route_id,
            rate_limiter=await self._shared_rate_limiter(),
        )
        await compiled.initialize()
        return compiled

    async def neutral_runtime(self) -> policy_runtime.MessagePolicyRuntime:
        if self._neutral is None:
            self._neutral = await self.compile(schema.neutral_policy())
        return self._neutral

    async def get_runtime(
        self,
        execution_context: typing.Any,
        bot_uuid: str | None,
        *,
        route_id: str | None = None,
        pipeline_uuid: str | None = None,
    ) -> policy_runtime.MessagePolicyRuntime:
        """Return the cached runtime for a bot route, compiling it on first use."""
        bot_entity = self._find_bot_entity(execution_context, bot_uuid)
        if bot_entity is None:
            return await self.neutral_runtime()

        route = select_route(
            getattr(bot_entity, 'event_bindings', None), route_id=route_id, pipeline_uuid=pipeline_uuid
        )
        route_key = str(route.get('id') or '') if route else _DEFAULT_ROUTE
        if route is not None and not route_key:
            # A route without an id cannot be cached apart from its siblings.
            route_key = 'target:' + str(route.get('target_uuid') or '')
        cache_key = (str(getattr(execution_context, 'workspace_uuid', '') or ''), str(bot_uuid))

        async with self._lock:
            cache = self._bots.get(cache_key)
            if cache is None or cache.bot_entity is not bot_entity:
                cache = _BotCache(bot_entity)
                self._bots[cache_key] = cache
            compiled = cache.runtimes.get(route_key)
            if compiled is None:
                compiled = await self.compile(
                    schema.resolve_policy(
                        getattr(bot_entity, 'message_policy', None),
                        route.get('policy') if route else None,
                    ),
                    bot_uuid=str(bot_uuid),
                    route_id=route_key or None,
                )
                cache.runtimes[route_key] = compiled
            return compiled

    async def bind_query(
        self,
        query: pipeline_query.Query,
        config: typing.Any = None,
    ) -> policy_runtime.MessagePolicyRuntime:
        """Resolve the policy of a query and lay it over its processor config."""
        from ..pipeline.pool import get_query_execution_context

        try:
            execution_context = get_query_execution_context(query)
        except Exception:
            execution_context = None
        variables = query.variables if isinstance(getattr(query, 'variables', None), dict) else {}
        route_id = variables.get(ROUTE_VARIABLE)
        compiled = await self.get_runtime(
            execution_context,
            getattr(query, 'bot_uuid', None),
            route_id=str(route_id) if route_id else None,
            pipeline_uuid=getattr(query, 'pipeline_uuid', None),
        )
        compiled.attach(query, config)
        return compiled

    async def for_query(self, query: pipeline_query.Query) -> policy_runtime.MessagePolicyRuntime:
        """Return the policy bound to a query, binding it first when needed."""
        bound = get_query_policy(query)
        if bound is not None:
            return bound
        return await self.bind_query(query)

    # ------------------------------------------------------------ invalidation

    def invalidate_bot(self, workspace_uuid: str, bot_uuid: str) -> None:
        """Forget the compiled policies of a bot after it was saved or removed."""
        self._bots.pop((str(workspace_uuid or ''), str(bot_uuid)), None)

    def invalidate_all(self) -> None:
        self._bots.clear()
