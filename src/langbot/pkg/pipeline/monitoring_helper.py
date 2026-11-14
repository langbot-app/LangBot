"""
Monitoring helper for recording events during pipeline execution.
This module provides convenient methods to record monitoring data
without cluttering the main pipeline code.
"""

from __future__ import annotations

import asyncio
import traceback
import typing
import time
import json

if typing.TYPE_CHECKING:
    from ..core import app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from .pool import get_query_execution_context

# Query variable naming the plugin (``author/name``) that owns a Host-built
# Query. Such Queries back plugin actions that did not originate in a pipeline
# and therefore carry no launcher/session identity of their own.
PLUGIN_ATTRIBUTION_VAR = '_monitoring_plugin'


def monitoring_platform(query: typing.Any) -> str | None:
    """Return the launcher type recorded as monitoring platform, if any."""
    launcher_type = getattr(query, 'launcher_type', None)
    if launcher_type is None:
        return None
    return launcher_type.value if hasattr(launcher_type, 'value') else str(launcher_type)


# Who handled a monitored message: ``runner:<runner_id>`` or ``plugin:<author>/<name>``.
HANDLED_BY_VAR = '_monitoring_handled_by'
# Monitoring identity of the pipeline Query that caused a plugin action.
ORIGIN_VAR = '_monitoring_origin'
UNKNOWN_PLUGIN_HANDLER = 'plugin:unknown'


def runner_handler(runner_id: str) -> str:
    return f'runner:{runner_id}'


def plugin_handler(author: str, name: str) -> str:
    return f'plugin:{author}/{name}'


def is_plugin_handler(handled_by: str | None) -> bool:
    return bool(handled_by) and handled_by.startswith('plugin:')


# Stages that drop a message by pipeline rule (access control, group respond
# rules, ignore rules / content filter, rate limit). They interrupt silently,
# so monitoring records where the message stopped as ``filtered:<stage>``.
FILTERED_HANDLER_PREFIX = 'filtered:'
FILTER_STAGES = frozenset(
    {
        'BanSessionCheckStage',
        'GroupRespondRuleCheckStage',
        'PreContentFilterStage',
        'PostContentFilterStage',
        'RequireRateLimitOccupancy',
    }
)


def filtered_handler(stage_name: str) -> str:
    return f'{FILTERED_HANDLER_PREFIX}{stage_name}'


def is_filtered_handler(handled_by: str | None) -> bool:
    return bool(handled_by) and handled_by.startswith(FILTERED_HANDLER_PREFIX)


def mark_stage_interrupt(query: typing.Any, stage_name: str) -> None:
    """Record that a filter stage stopped this Query, unless someone already handled it."""
    if stage_name not in FILTER_STAGES or get_handled_by(query):
        return
    mark_handled_by(query, filtered_handler(stage_name))


def mark_handled_by(query: typing.Any, handled_by: str | None) -> None:
    """Remember who handled this Query; written when the message is finished."""
    if not handled_by:
        return
    if getattr(query, 'variables', None) is None:
        query.variables = {}
    query.variables[HANDLED_BY_VAR] = handled_by


def mark_plugin_handled(query: typing.Any, event_ctx: typing.Any) -> None:
    """Attribute a Query whose default processing a plugin prevented."""
    from . import plugin_diagnostics

    plugin_ref = plugin_diagnostics.get_prevent_default_plugin(event_ctx)
    mark_handled_by(
        query,
        plugin_handler(plugin_ref['author'], plugin_ref['name']) if plugin_ref else UNKNOWN_PLUGIN_HANDLER,
    )


def get_handled_by(query: typing.Any) -> str | None:
    return (getattr(query, 'variables', None) or {}).get(HANDLED_BY_VAR)


def _origin(query: typing.Any) -> dict:
    origin = (getattr(query, 'variables', None) or {}).get(ORIGIN_VAR)
    return origin if isinstance(origin, dict) else {}


def monitoring_session_id(query: typing.Any) -> str:
    """Return the monitoring session id for pipeline and plugin-owned Queries."""
    platform = monitoring_platform(query)
    if platform is not None:
        launcher_id = getattr(query, 'launcher_id', None)
        sender_id = getattr(query, 'sender_id', None)
        if platform == 'group' and sender_id not in (None, ''):
            return f'{platform}_{launcher_id}_{sender_id}'
        return f'{platform}_{launcher_id}'
    if _origin(query).get('session_id'):
        return _origin(query)['session_id']
    plugin = (getattr(query, 'variables', None) or {}).get(PLUGIN_ATTRIBUTION_VAR)
    return f'plugin:{plugin}' if plugin else 'unknown'


def monitoring_bot_id(query: typing.Any) -> str:
    return getattr(query, 'bot_uuid', None) or _origin(query).get('bot_id') or 'unknown'


def monitoring_pipeline_id(query: typing.Any) -> str:
    return getattr(query, 'pipeline_uuid', None) or _origin(query).get('pipeline_id') or 'unknown'


def attribute_to_origin(query: typing.Any, origin: typing.Any) -> None:
    """Attribute a plugin-owned Query's monitoring records to the triggering Query.

    Attribution only: the plugin Query keeps its own (plugin) authority and
    never inherits the origin's pipeline configuration or resources.
    """
    origin_variables = getattr(origin, 'variables', None) or {}
    if getattr(query, 'variables', None) is None:
        query.variables = {}
    query.variables[ORIGIN_VAR] = {
        'bot_id': getattr(origin, 'bot_uuid', None),
        'pipeline_id': getattr(origin, 'pipeline_uuid', None),
        'session_id': monitoring_session_id(origin),
    }
    for key in ('_monitoring_message_id', '_monitoring_bot_name', '_monitoring_pipeline_name'):
        if origin_variables.get(key):
            query.variables[key] = origin_variables[key]


async def resolve_processor_name(
    ap: app.Application,
    workspace_uuid: str,
    processor_type: str,
    processor_id: str | None,
    runner_id: str = '',
) -> str:
    """Display name of the processor kind that handled a run.

    Monitoring attributed every call to a Pipeline, so an Agent or a plugin event
    processor recorded "Unknown" for the entity that actually ran. Each kind is
    resolved from the table that owns it, falling back to the identity the
    binding carried.
    """
    import sqlalchemy

    from ..entity.persistence import agent as persistence_agent
    from ..entity.persistence import pipeline as persistence_pipeline

    identifier = str(processor_id or '').strip()
    if identifier:
        try:
            model = persistence_pipeline.LegacyPipeline if processor_type == 'pipeline' else persistence_agent.Agent
            result = await ap.persistence_mgr.execute_async(
                sqlalchemy.select(model.name).where(
                    sqlalchemy.and_(
                        model.uuid == identifier,
                        model.workspace_uuid == workspace_uuid,
                    )
                )
            )
            name = str(result.scalar() or '').strip()
            if name:
                return name
        except Exception as e:
            ap.logger.warning(f'Failed to resolve monitoring processor name: {e}')
    # A deleted Agent or an unregistered plugin processor still names the
    # component that ran, never a bare "Unknown".
    return identifier or runner_id or processor_type


async def prepare_monitoring_identity(
    ap: app.Application,
    query: pipeline_query.Query,
    *,
    processor_type: str,
    processor_id: str | None,
    runner_id: str = '',
    execution_record_id: str = '',
) -> None:
    """Pin the monitoring identity of a runner-owned execution.

    A Pipeline pins these variables when it starts a query; a Runner started by
    an Agent or a plugin event processor has to pin them itself, otherwise every
    LLM/tool call it makes is attributed to "Unknown". An enclosing Pipeline
    already named the run, so its label is never overwritten.

    ``_monitoring_message_id`` is the execution record the calls belong to: the
    Pipeline's message, or the Agent run's id. Both are the id the executions
    list shows, which is what lets a call jump back to its record.
    """
    try:
        variables = getattr(query, 'variables', None)
        if not isinstance(variables, dict):
            return
        if variables.get('_monitoring_pipeline_name'):
            return

        bot_name = 'WebChat'
        bot_uuid = str(getattr(query, 'bot_uuid', '') or '')
        workspace_uuid = str(getattr(query, 'workspace_uuid', '') or '')
        if bot_uuid and workspace_uuid:
            try:
                bot = await ap.bot_service.get_bot(
                    workspace_uuid,
                    bot_uuid,
                    include_secret=False,
                )
                if bot:
                    bot_name = bot.get('name', bot_name)
            except Exception as e:
                ap.logger.warning(f'Failed to resolve monitoring bot name: {e}')

        variables['_monitoring_bot_name'] = bot_name
        variables['_monitoring_pipeline_name'] = await resolve_processor_name(
            ap,
            workspace_uuid,
            processor_type,
            processor_id,
            runner_id,
        )
        if execution_record_id:
            variables['_monitoring_message_id'] = execution_record_id
    except Exception as e:
        ap.logger.error(f'Failed to prepare monitoring identity: {e}')


class MonitoringHelper:
    """Helper class for monitoring operations"""

    @staticmethod
    def _build_session_id(query: pipeline_query.Query) -> str:
        return monitoring_session_id(query)

    @staticmethod
    def _extract_sender_name(query: pipeline_query.Query) -> str | None:
        """Extract session display name from query message event."""
        sender_name: str | None = None

        message_event = getattr(query, 'message_event', None)
        group = getattr(message_event, 'group', None)
        group_name = getattr(group, 'name', None) if group is not None else None
        if isinstance(group_name, str) and group_name.strip():
            return group_name.strip()

        sender = getattr(message_event, 'sender', None)
        if sender is not None:
            get_name = getattr(sender, 'get_name', None)
            if callable(get_name):
                try:
                    sender_name = get_name()
                except Exception:
                    sender_name = None
                else:
                    sender_name = sender_name.strip() if isinstance(sender_name, str) else None

            if not sender_name:
                for attr in (
                    'member_name',
                    'nickname',
                    'remark',
                    'name',
                    'display_name',
                    'username',
                    'user_name',
                    'card',
                ):
                    value = getattr(sender, attr, None)
                    if isinstance(value, str) and value.strip():
                        sender_name = value.strip()
                        break

        if not sender_name:
            variables = getattr(query, 'variables', None)
            if isinstance(variables, dict):
                var_sender_name = variables.get('sender_name')
                if isinstance(var_sender_name, str) and var_sender_name.strip():
                    sender_name = var_sender_name.strip()

        return sender_name if sender_name else None

    @staticmethod
    async def finish_query(ap, query, message_id: str, status: str) -> None:
        """Bound terminal writes and retry transient failures without blocking cleanup."""
        if not message_id:
            return
        handled_by = get_handled_by(query)
        attribution = {}
        if handled_by:
            # A plugin that took the message over, or a filter stage that dropped
            # it, means the runner never ran.
            attribution = {
                'handled_by': handled_by,
                'clear_runner_name': is_plugin_handler(handled_by) or is_filtered_handler(handled_by),
            }
        for attempt in range(3):
            try:
                async with asyncio.timeout(2):
                    await ap.monitoring_service.update_message_status(
                        get_query_execution_context(query),
                        message_id=message_id,
                        status=status,
                        level='error' if status == 'error' else 'info',
                        **attribution,
                    )
                return
            except Exception as exc:
                ap.logger.warning(f'Terminal monitoring write failed (attempt {attempt + 1}): {exc}')
        ap.logger.error(f'Unable to finish monitoring message {message_id}: {status}')

    @staticmethod
    async def record_query_start(
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        runner_name: str | None = None,
    ) -> str:
        """Record the start of query processing, returns message_id"""
        try:
            # Message persistence updates the summary in the same transaction.
            session_id = monitoring_session_id(query)
            sender_name = MonitoringHelper._extract_sender_name(query)

            # Try to record message
            # Let persistence externalize images before serializing the message chain.
            if hasattr(query, 'message_chain') and hasattr(query.message_chain, 'model_dump'):
                message_content = query.message_chain.model_dump()
            else:
                message_content = str(query)

            # Variables will be updated in record_query_success after preproc stage sets them
            # Here we just record None, the full variables will be set when query completes

            message_id = await ap.monitoring_service.record_message(
                get_query_execution_context(query),
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                message_content=message_content,
                session_id=session_id,
                status='pending',
                level='info',
                platform=monitoring_platform(query),
                user_id=getattr(query, 'sender_id', None),
                user_name=sender_name,
                runner_name=runner_name,
                variables=None,  # Will be updated in record_query_success
            )

            return message_id
        except Exception as e:
            ap.logger.error(f'Failed to record query start: {e}')
            return ''

    @staticmethod
    async def record_query_success(
        ap: app.Application,
        message_id: str,
        query: pipeline_query.Query | None = None,
    ):
        """Record successful query processing by updating message status and variables"""
        try:
            if message_id:
                # Serialize query.variables (filtering out internal variables)
                query_variables_str = None
                if query and hasattr(query, 'variables') and query.variables:
                    filtered_vars = {k: v for k, v in query.variables.items() if not k.startswith('_')}
                    if filtered_vars:
                        try:
                            query_variables_str = json.dumps(filtered_vars, ensure_ascii=False, default=str)
                        except Exception:
                            pass

                await ap.monitoring_service.update_message_status(
                    get_query_execution_context(query),
                    message_id=message_id,
                    status='success',
                    variables=query_variables_str,
                )
        except Exception as e:
            ap.logger.error(f'Failed to record query success: {e}')

    @staticmethod
    async def record_query_response(
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        runner_name: str | None = None,
    ):
        """Record bot response message to monitoring"""
        try:
            handled_by = get_handled_by(query)
            session_id = monitoring_session_id(query)
            sender_name = MonitoringHelper._extract_sender_name(query)

            # Extract response content from resp_message_chain
            if hasattr(query, 'resp_message_chain') and query.resp_message_chain:
                # Preserve the structure until persistence has externalized images.
                last_resp = query.resp_message_chain[-1]
                if hasattr(last_resp, 'model_dump'):
                    message_content = last_resp.model_dump()
                else:
                    message_content = str(last_resp)
            elif hasattr(query, 'resp_messages') and query.resp_messages:
                last_resp = query.resp_messages[-1]
                if hasattr(last_resp, 'get_content_platform_message_chain'):
                    chain = last_resp.get_content_platform_message_chain()
                    if hasattr(chain, 'model_dump'):
                        message_content = chain.model_dump()
                    else:
                        message_content = str(chain)
                else:
                    message_content = str(last_resp)
            else:
                return  # No response to record

            await ap.monitoring_service.record_message(
                get_query_execution_context(query),
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                message_content=message_content,
                session_id=session_id,
                status='success',
                level='info',
                platform=monitoring_platform(query),
                user_id=getattr(query, 'sender_id', None),
                user_name=sender_name,
                runner_name=None if is_plugin_handler(handled_by) else runner_name,
                role='assistant',
                parent_message_id=(query.variables or {}).get('_monitoring_message_id'),
                **({'handled_by': handled_by} if handled_by else {}),
            )
        except Exception as e:
            ap.logger.error(f'Failed to record query response: {e}')

    @staticmethod
    async def record_query_error(
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        error: Exception,
        runner_name: str | None = None,
    ) -> str:
        """Record query processing error, returns message_id"""
        try:
            original_message_id = (query.variables or {}).get('_monitoring_message_id')
            if original_message_id:
                await MonitoringHelper.finish_query(ap, query, original_message_id, 'error')
            session_id = monitoring_session_id(query)
            sender_name = MonitoringHelper._extract_sender_name(query)

            # Record error message
            message_id = await ap.monitoring_service.record_message(
                get_query_execution_context(query),
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                message_content=f'Error: {str(error)}',
                role='assistant',
                session_id=session_id,
                status='error',
                level='error',
                platform=monitoring_platform(query),
                user_id=getattr(query, 'sender_id', None),
                user_name=sender_name,
                runner_name=runner_name,
            )

            # Record error log
            await ap.monitoring_service.record_error(
                get_query_execution_context(query),
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                error_type=type(error).__name__,
                error_message=str(error),
                session_id=session_id,
                stack_trace=traceback.format_exc(),
                message_id=message_id,
            )

            return message_id
        except Exception as e:
            ap.logger.error(f'Failed to record query error: {e}')
            return ''

    @staticmethod
    async def record_plugin_message(
        ap: app.Application,
        context: typing.Any,
        *,
        plugin: str,
        message_chain: typing.Any,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        session_id: str,
        platform: str | None,
        user_id: str | None = None,
        user_name: str | None = None,
        parent_message_id: str | None = None,
        error: BaseException | None = None,
        error_type: str = 'PluginDeliveryError',
    ) -> str:
        """Record a message a plugin delivered itself (``ctx.reply``/``send_message``).

        Monitoring must never change delivery behaviour, so failures here are
        logged and swallowed.
        """
        try:
            content = message_chain.model_dump() if hasattr(message_chain, 'model_dump') else str(message_chain)
            message_id = await ap.monitoring_service.record_message(
                context,
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                message_content=content,
                session_id=session_id,
                status='error' if error is not None else 'success',
                level='error' if error is not None else 'info',
                platform=platform,
                user_id=user_id,
                user_name=user_name,
                runner_name=None,
                role='assistant',
                parent_message_id=parent_message_id,
                handled_by=plugin,
            )
            if error is not None:
                await ap.monitoring_service.record_error(
                    context,
                    bot_id=bot_id,
                    bot_name=bot_name,
                    pipeline_id=pipeline_id,
                    pipeline_name=pipeline_name,
                    error_type=error_type,
                    error_message=f'{plugin}: {type(error).__name__}: {error}',
                    session_id=session_id,
                    stack_trace=''.join(traceback.format_exception(error)),
                    message_id=message_id,
                )
            return message_id
        except Exception as exc:
            ap.logger.error(f'Failed to record plugin message: {exc}')
            return ''

    @staticmethod
    async def record_plugin_reply(
        ap: app.Application,
        query: typing.Any,
        plugin: str,
        message_chain: typing.Any,
        error: BaseException | None = None,
    ) -> str:
        """Record a ``ctx.reply`` from a plugin as a reply to the triggering message."""
        variables = getattr(query, 'variables', None) or {}
        return await MonitoringHelper.record_plugin_message(
            ap,
            get_query_execution_context(query),
            plugin=plugin,
            message_chain=message_chain,
            bot_id=monitoring_bot_id(query),
            bot_name=variables.get('_monitoring_bot_name', 'Unknown'),
            pipeline_id=monitoring_pipeline_id(query),
            pipeline_name=variables.get('_monitoring_pipeline_name', 'Unknown'),
            session_id=monitoring_session_id(query),
            platform=monitoring_platform(query),
            user_id=getattr(query, 'sender_id', None),
            user_name=MonitoringHelper._extract_sender_name(query),
            parent_message_id=variables.get('_monitoring_message_id'),
            error=error,
            error_type='PluginReplyError',
        )

    @staticmethod
    async def record_llm_call(
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        status: str = 'success',
        cost: float | None = None,
        error_message: str | None = None,
        message_id: str | None = None,
        details: dict | None = None,
    ):
        """Record LLM call"""
        try:
            session_id = monitoring_session_id(query)

            await ap.monitoring_service.record_llm_call(
                get_query_execution_context(query),
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                session_id=session_id,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration=duration_ms,
                status=status,
                cost=cost,
                error_message=error_message,
                message_id=message_id,
                details=details,
            )
        except Exception as e:
            ap.logger.error(f'Failed to record LLM call: {e}')


class LLMCallMonitor:
    """Context manager for monitoring LLM calls"""

    def __init__(
        self,
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        model_name: str,
    ):
        self.ap = ap
        self.query = query
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.pipeline_id = pipeline_id
        self.pipeline_name = pipeline_name
        self.model_name = model_name
        self.start_time = None
        self.input_tokens = 0
        self.output_tokens = 0

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self.start_time) * 1000)

        if exc_type is not None:
            # Error occurred
            await MonitoringHelper.record_llm_call(
                ap=self.ap,
                query=self.query,
                bot_id=self.bot_id,
                bot_name=self.bot_name,
                pipeline_id=self.pipeline_id,
                pipeline_name=self.pipeline_name,
                model_name=self.model_name,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                duration_ms=duration_ms,
                status='error',
                error_message=str(exc_val) if exc_val else None,
            )
        else:
            # Success
            await MonitoringHelper.record_llm_call(
                ap=self.ap,
                query=self.query,
                bot_id=self.bot_id,
                bot_name=self.bot_name,
                pipeline_id=self.pipeline_id,
                pipeline_name=self.pipeline_name,
                model_name=self.model_name,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                duration_ms=duration_ms,
                status='success',
            )

        return False  # Don't suppress exceptions
