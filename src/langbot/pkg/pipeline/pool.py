from __future__ import annotations

import asyncio
import dataclasses
import inspect
import typing
import uuid

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from ..api.http.context import ExecutionContext

QueryCacheKey = tuple[str, str]
LegacyQueryKey = tuple[str, int]
QueryCounterKey = tuple[str, str, int]
SingletonContextResolver = typing.Callable[
    [],
    ExecutionContext | typing.Awaitable[ExecutionContext],
]


class ExecutionContextRequiredError(ValueError):
    """Raised when runtime work is created without a trusted Workspace scope."""


class ExecutionContextMismatchError(ValueError):
    """Raised when entity fields conflict with their trusted execution scope."""


class QueryNotFoundError(LookupError):
    """Raised when a query does not exist inside the requested Workspace."""


def _validate_execution_context(execution_context: ExecutionContext) -> None:
    if not isinstance(execution_context, ExecutionContext):
        raise ExecutionContextRequiredError('A trusted ExecutionContext is required')
    if not isinstance(execution_context.instance_uuid, str) or not execution_context.instance_uuid.strip():
        raise ExecutionContextRequiredError('ExecutionContext.instance_uuid is required')
    if not isinstance(execution_context.workspace_uuid, str) or not execution_context.workspace_uuid.strip():
        raise ExecutionContextRequiredError('ExecutionContext.workspace_uuid is required')
    if (
        isinstance(execution_context.placement_generation, bool)
        or not isinstance(execution_context.placement_generation, int)
        or execution_context.placement_generation <= 0
    ):
        raise ExecutionContextRequiredError('ExecutionContext.placement_generation must be a positive integer')
    for field_name in ('bot_uuid', 'pipeline_uuid', 'query_uuid'):
        value = getattr(execution_context, field_name)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ExecutionContextRequiredError(f'ExecutionContext.{field_name} must be a non-empty string when set')


def bind_execution_context(
    execution_context: ExecutionContext,
    *,
    bot_uuid: str | None = None,
    pipeline_uuid: str | None = None,
    query_uuid: str | None = None,
) -> ExecutionContext:
    """Bind runtime entity identifiers without allowing scope substitution."""

    _validate_execution_context(execution_context)

    requested_fields = {
        'bot_uuid': bot_uuid,
        'pipeline_uuid': pipeline_uuid,
        'query_uuid': query_uuid,
    }
    updates: dict[str, str] = {}
    for field_name, requested_value in requested_fields.items():
        if requested_value is None:
            continue
        if not isinstance(requested_value, str) or not requested_value.strip():
            raise ExecutionContextRequiredError(f'{field_name} must be a non-empty string')
        current_value = getattr(execution_context, field_name)
        if current_value is not None and current_value != requested_value:
            raise ExecutionContextMismatchError(f'ExecutionContext.{field_name} does not match the runtime entity')
        if current_value is None:
            updates[field_name] = requested_value

    if not updates:
        return execution_context
    return dataclasses.replace(execution_context, **updates)


def get_query_execution_context(query: pipeline_query.Query) -> ExecutionContext:
    """Return and validate the trusted context attached to a Query."""

    attached_context = getattr(query, '_execution_context', None)
    bot_uuid = getattr(query, 'bot_uuid', None)
    pipeline_uuid = getattr(query, 'pipeline_uuid', None)
    query_uuid = getattr(query, 'query_uuid', None)

    if isinstance(attached_context, ExecutionContext):
        return bind_execution_context(
            attached_context,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
            query_uuid=query_uuid,
        )

    raise ExecutionContextRequiredError('Query is missing its trusted ExecutionContext')


class QueryPool:
    """Workspace-scoped queue of requests waiting for pipeline scheduling."""

    query_id_counter: int
    pool_lock: asyncio.Lock
    queries: list[pipeline_query.Query]
    cached_queries: dict[QueryCacheKey, pipeline_query.Query]
    legacy_query_index: dict[LegacyQueryKey, str]
    query_count_by_scope: dict[QueryCounterKey, int]
    condition: asyncio.Condition

    def __init__(
        self,
        singleton_context_resolver: SingletonContextResolver | None = None,
    ):
        self.query_id_counter = 0
        self.pool_lock = asyncio.Lock()
        self.queries = []
        self.cached_queries = {}
        self.legacy_query_index = {}
        self.query_count_by_scope = {}
        self.condition = asyncio.Condition(self.pool_lock)
        self._singleton_context_resolver = singleton_context_resolver

    async def resolve_execution_context(
        self,
        execution_context: ExecutionContext | None,
        *,
        bot_uuid: str,
        pipeline_uuid: str | None,
        query_uuid: str | None = None,
    ) -> ExecutionContext:
        """Resolve an explicit scope or the opt-in OSS singleton scope."""

        if execution_context is None:
            if self._singleton_context_resolver is None:
                raise ExecutionContextRequiredError('ExecutionContext is required; no singleton resolver is configured')
            resolved_context = self._singleton_context_resolver()
            if inspect.isawaitable(resolved_context):
                resolved_context = await resolved_context
            execution_context = resolved_context

        return bind_execution_context(
            execution_context,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
            query_uuid=query_uuid,
        )

    async def add_query(
        self,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: int | str,
        sender_id: int | str,
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        pipeline_uuid: str | None = None,
        routed_by_rule: bool = False,
        variables: dict[str, typing.Any] | None = None,
        execution_context: ExecutionContext | None = None,
    ) -> pipeline_query.Query:
        """Create a query and cache it under an opaque, Workspace-scoped key."""

        query_uuid = str(uuid.uuid4())
        execution_context = await self.resolve_execution_context(
            execution_context,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
            query_uuid=query_uuid,
        )

        async with self.condition:
            query_id = self.query_id_counter
            initial_variables: dict[str, typing.Any] = {'_routed_by_rule': routed_by_rule}
            if variables:
                initial_variables.update(variables)
            query = pipeline_query.Query(
                instance_uuid=execution_context.instance_uuid,
                workspace_uuid=execution_context.workspace_uuid,
                placement_generation=execution_context.placement_generation,
                bot_uuid=bot_uuid,
                query_id=query_id,
                query_uuid=query_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=sender_id,
                message_event=message_event,
                message_chain=message_chain,
                variables=initial_variables,
                resp_messages=[],
                resp_message_chain=[],
                adapter=adapter,
                pipeline_uuid=pipeline_uuid,
            )

            # langbot-plugin 0.4.13 ignores these forward-compatible fields.
            # Attach them explicitly until the Workspace-aware SDK is released.
            object.__setattr__(query, 'instance_uuid', execution_context.instance_uuid)
            object.__setattr__(query, 'workspace_uuid', execution_context.workspace_uuid)
            object.__setattr__(
                query,
                'placement_generation',
                execution_context.placement_generation,
            )
            object.__setattr__(query, 'query_uuid', query_uuid)
            object.__setattr__(query, '_execution_context', execution_context)

            self.queries.append(query)
            self.cached_queries[(execution_context.workspace_uuid, query_uuid)] = query
            self.legacy_query_index[(execution_context.workspace_uuid, query_id)] = query_uuid
            self.query_id_counter += 1
            counter_key = (
                execution_context.instance_uuid,
                execution_context.workspace_uuid,
                execution_context.placement_generation,
            )
            self.query_count_by_scope[counter_key] = self.query_count_by_scope.get(counter_key, 0) + 1
            self.condition.notify_all()
            return query

    def get_query_count(self, execution_context: ExecutionContext) -> int:
        """Return the lifetime query count for one active placement scope."""

        _validate_execution_context(execution_context)
        return self.query_count_by_scope.get(
            (
                execution_context.instance_uuid,
                execution_context.workspace_uuid,
                execution_context.placement_generation,
            ),
            0,
        )

    async def get_query(
        self,
        workspace_uuid: str,
        query_uuid: str,
    ) -> pipeline_query.Query | None:
        """Return a query only from the explicitly selected Workspace."""

        async with self.pool_lock:
            return self.cached_queries.get((workspace_uuid, query_uuid))

    async def require_query(
        self,
        workspace_uuid: str,
        query_uuid: str,
    ) -> pipeline_query.Query:
        """Return a scoped query or raise without checking other Workspaces."""

        query = await self.get_query(workspace_uuid, query_uuid)
        if query is None:
            raise QueryNotFoundError(f'Query {query_uuid!r} was not found in Workspace {workspace_uuid!r}')
        return query

    async def get_query_by_legacy_id(
        self,
        workspace_uuid: str,
        query_id: int,
    ) -> pipeline_query.Query | None:
        """Resolve a legacy integer ID within one explicit Workspace."""

        async with self.pool_lock:
            query_uuid = self.legacy_query_index.get((workspace_uuid, query_id))
            if query_uuid is None:
                return None
            return self.cached_queries.get((workspace_uuid, query_uuid))

    async def remove_query(self, query: pipeline_query.Query) -> bool:
        """Remove a query and both of its Workspace-scoped indexes."""

        execution_context = get_query_execution_context(query)
        query_uuid = execution_context.query_uuid
        if query_uuid is None:
            raise ExecutionContextRequiredError('Query.query_uuid is required for removal')

        async with self.pool_lock:
            cache_key = (execution_context.workspace_uuid, query_uuid)
            cached_query = self.cached_queries.get(cache_key)
            if cached_query is not query:
                return False
            del self.cached_queries[cache_key]
            self.legacy_query_index.pop(
                (execution_context.workspace_uuid, query.query_id),
                None,
            )
            for index, queued_query in enumerate(self.queries):
                if queued_query is query:
                    self.queries.pop(index)
                    break
            return True

    async def __aenter__(self):
        await self.pool_lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.pool_lock.release()
