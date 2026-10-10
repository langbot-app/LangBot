from __future__ import annotations

import datetime
import quart

from ...authz import Permission
from ...context import RequestContext
from ...service.monitoring_traffic import get_traffic_series
from .. import group


def parse_iso_datetime(datetime_str: str | None) -> datetime.datetime | None:
    """Parse ISO 8601 datetime string, handling 'Z' suffix for UTC timezone"""
    if not datetime_str:
        return None
    # Replace 'Z' with '+00:00' for Python 3.10 compatibility
    if datetime_str.endswith('Z'):
        datetime_str = datetime_str[:-1] + '+00:00'
    dt = datetime.datetime.fromisoformat(datetime_str)
    # Convert to UTC and remove timezone info to match database storage (which stores UTC as naive datetime)
    if dt.tzinfo is not None:
        # Convert to UTC and remove timezone info
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


def validate_monitoring_window(start_time: datetime.datetime | None, end_time: datetime.datetime | None) -> None:
    """Bound explicit dashboard windows to one year without silently truncating them."""
    if start_time is None:
        return
    end = end_time or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    if start_time >= end or end - start_time > datetime.timedelta(days=365):
        quart.abort(400, description='Monitoring time range must be positive and no longer than 365 days')

@group.group_class('monitoring', '/api/v1/monitoring')
class MonitoringRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/overview', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_overview(request_context: RequestContext) -> str:
            """Get overview metrics"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            metrics = await self.ap.monitoring_service.get_overview_metrics(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
            )

            return self.success(data=metrics)

        @self.route('/in-flight/stream', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def stream_inflight(request_context: RequestContext):
            from .....utils.inflight import inflight_hub
            from ...service.tenant import require_workspace_uuid
            import json

            workspace = require_workspace_uuid(request_context)
            previous = []

            async def snapshot():
                nonlocal previous
                result = await self.ap.monitoring_service.get_inflight_snapshot(request_context, previous)
                previous = [row for row in result['items'] if row['status_group'] in {'running', 'queued'}]
                return result

            async def frames():
                async for frame in inflight_hub.watch(workspace, snapshot):
                    yield 'data: ' + json.dumps(frame, ensure_ascii=False) + '\n\n'

            response = quart.Response(frames(), content_type='text/event-stream')
            response.headers['Cache-Control'] = 'no-cache, no-store'
            response.headers['X-Accel-Buffering'] = 'no'
            response.timeout = None
            return response

        @self.route('/executions', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_executions(request_context: RequestContext) -> str:
            """Unified execution list across agent runs and pipeline queries."""
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            agent_ids = quart.request.args.getlist('agentId')
            statuses = quart.request.args.getlist('status')
            source = quart.request.args.get('source', 'all')
            mode = quart.request.args.get('mode', 'all')
            start_time = parse_iso_datetime(quart.request.args.get('startTime'))
            end_time = parse_iso_datetime(quart.request.args.get('endTime'))
            validate_monitoring_window(start_time, end_time)

            result = await self.ap.monitoring_service.get_executions(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                agent_ids=agent_ids if agent_ids else None,
                statuses=statuses if statuses else None,
                source=source,
                mode=mode,
                start_time=start_time,
                end_time=end_time,
                limit=quart.request.args.get('limit', 50),
                offset=quart.request.args.get('offset', 0),
            )

            return self.success(data=result)

        @self.route(
            '/executions/<source>/<execution_id>',
            methods=['GET'],
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_execution_detail(source: str, execution_id: str, request_context: RequestContext) -> str:
            """Full trace of a single execution (agent run or pipeline query)."""
            try:
                detail = await self.ap.monitoring_service.get_execution_detail(
                    request_context,
                    source,
                    execution_id,
                    section=quart.request.args.get('section'),
                    offset=quart.request.args.get('offset', 0),
                    limit=quart.request.args.get('limit', 100),
                )
            except ValueError as exc:
                return self.fail(404, str(exc))
            return self.success(data=detail)

        @self.route('/token-statistics', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_token_statistics(request_context: RequestContext) -> str:
            """Get detailed token usage statistics (summary, per-model, timeseries)."""
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            bucket = quart.request.args.get('bucket', 'hour')
            if bucket not in ('hour', 'day'):
                bucket = 'hour'

            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            stats = await self.ap.monitoring_service.get_token_statistics(
                request_context,
                execution_statuses=quart.request.args.getlist('status') or None,
                mode=quart.request.args.get('mode', 'all'),
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                bucket=bucket,
            )

            return self.success(data=stats)

        @self.route(
            '/messages',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_messages(request_context: RequestContext) -> str:
            """Get message logs"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            session_ids = quart.request.args.getlist('sessionId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit, offset = self.ap.monitoring_service.normalize_page_window(
                quart.request.args.get('limit', 100), quart.request.args.get('offset', 0)
            )

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            messages, total = await self.ap.monitoring_service.get_messages(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                session_ids=session_ids if session_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset,
            )

            return self.success(
                data={
                    'messages': messages,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            )

        @self.route(
            '/llm-calls',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_llm_calls(request_context: RequestContext) -> str:
            """Get LLM call records"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit, offset = self.ap.monitoring_service.normalize_page_window(
                quart.request.args.get('limit', 100), quart.request.args.get('offset', 0)
            )

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            llm_calls, total = await self.ap.monitoring_service.get_llm_calls(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset,
            )

            return self.success(
                data={
                    'llm_calls': llm_calls,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            )

        @self.route(
            '/tool-calls',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_tool_calls(request_context: RequestContext) -> str:
            """Get tool call records"""
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            session_ids = quart.request.args.getlist('sessionId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit, offset = self.ap.monitoring_service.normalize_page_window(
                quart.request.args.get('limit', 100), quart.request.args.get('offset', 0)
            )

            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            tool_calls, total = await self.ap.monitoring_service.get_tool_calls(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                session_ids=session_ids if session_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset,
            )

            return self.success(
                data={
                    'tool_calls': tool_calls,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            )

        @self.route(
            '/embedding-calls',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_embedding_calls(request_context: RequestContext) -> str:
            """Get embedding call records"""
            # Parse query parameters
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            knowledge_base_id = quart.request.args.get('knowledgeBaseId')
            limit, offset = self.ap.monitoring_service.normalize_page_window(
                quart.request.args.get('limit', 100), quart.request.args.get('offset', 0)
            )

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            embedding_calls, total = await self.ap.monitoring_service.get_embedding_calls(
                request_context,
                start_time=start_time,
                end_time=end_time,
                knowledge_base_id=knowledge_base_id if knowledge_base_id else None,
                limit=limit,
                offset=offset,
            )

            return self.success(
                data={
                    'embedding_calls': embedding_calls,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            )

        @self.route(
            '/sessions',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_sessions(request_context: RequestContext) -> str:
            """Get session information"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            user_query = quart.request.args.get('userQuery')
            is_active_str = quart.request.args.get('isActive')
            limit, offset = self.ap.monitoring_service.normalize_page_window(
                quart.request.args.get('limit', 100), quart.request.args.get('offset', 0)
            )

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            # Parse is_active
            is_active = None
            if is_active_str:
                is_active = is_active_str.lower() == 'true'

            sessions, total = await self.ap.monitoring_service.get_sessions(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                user_query=user_query,
                is_active=is_active,
                limit=limit,
                offset=offset,
            )

            return self.success(
                data={
                    'sessions': sessions,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            )

        @self.route(
            '/errors',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_errors(request_context: RequestContext) -> str:
            """Get error logs"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit, offset = self.ap.monitoring_service.normalize_page_window(
                quart.request.args.get('limit', 100), quart.request.args.get('offset', 0)
            )

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            errors, total = await self.ap.monitoring_service.get_errors(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset,
            )

            return self.success(
                data={
                    'errors': errors,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            )

        @self.route('/data', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_all_data(request_context: RequestContext) -> str:
            """Get all monitoring data in a single request"""
            execution_filters = {
                'execution_statuses': quart.request.args.getlist('status') or None,
                'mode': quart.request.args.get('mode', 'all'),
            }
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 50))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            # Get overview metrics
            overview = await self.ap.monitoring_service.get_overview_metrics(
                request_context,
                **execution_filters,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
            )

            # Get messages
            messages, messages_total = await self.ap.monitoring_service.get_messages(
                request_context,
                **execution_filters,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=0,
            )

            # Get LLM calls
            llm_calls, llm_calls_total = await self.ap.monitoring_service.get_llm_calls(
                request_context,
                **execution_filters,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=0,
            )

            # Get tool calls
            tool_calls, tool_calls_total = await self.ap.monitoring_service.get_tool_calls(
                request_context,
                **execution_filters,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=0,
            )

            # Get sessions
            sessions, sessions_total = await self.ap.monitoring_service.get_sessions(
                request_context,
                **execution_filters,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                is_active=None,
                limit=limit,
                offset=0,
            )

            # Get errors
            errors, errors_total = await self.ap.monitoring_service.get_errors(
                request_context,
                **execution_filters,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=0,
            )

            # Get embedding calls
            embedding_calls, embedding_calls_total = await self.ap.monitoring_service.get_embedding_calls(
                request_context,
                **execution_filters,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=0,
            )

            return self.success(
                data={
                    'traffic': await get_traffic_series(
                        self.ap,
                        request_context,
                        **execution_filters,
                        bot_ids=bot_ids or None,
                        pipeline_ids=pipeline_ids or None,
                        start_time=start_time,
                        end_time=end_time,
                    ),
                    'overview': overview,
                    'messages': messages,
                    'llmCalls': llm_calls,
                    'toolCalls': tool_calls,
                    'embeddingCalls': embedding_calls,
                    'sessions': sessions,
                    'errors': errors,
                    'totalCount': {
                        'messages': messages_total,
                        'llmCalls': llm_calls_total,
                        'toolCalls': tool_calls_total,
                        'embeddingCalls': embedding_calls_total,
                        'sessions': sessions_total,
                        'errors': errors_total,
                    },
                }
            )

        @self.route('/sessions/reset-context', methods=['POST'],
                    auth_type=group.AuthType.USER_TOKEN_OR_API_KEY, permission=Permission.RESOURCE_MANAGE)
        async def reset_session_context(request_context: RequestContext):
            body = await quart.request.get_json()
            if not isinstance(body, dict):
                return self.http_status(400, 'invalid_request', 'Expected a JSON object')
            try:
                result = await self.ap.monitoring_service.reset_session_context(
                    request_context, body.get('bot_id'), body.get('session_id'),
                )
            except ValueError as exc:
                return self.http_status(400, 'invalid_request', str(exc))
            except LookupError as exc:
                return self.http_status(404, 'resource_not_found', str(exc))
            except RuntimeError as exc:
                return self.http_status(409, 'session_busy', str(exc))
            return self.success(data=result)

        @self.route(
            '/sessions/<session_id>/analysis',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_session_analysis(session_id: str, request_context: RequestContext) -> str:
            """Get detailed analysis for a specific session"""
            start_time = parse_iso_datetime(quart.request.args.get('startTime'))
            end_time = parse_iso_datetime(quart.request.args.get('endTime'))
            validate_monitoring_window(start_time, end_time)
            analysis = await self.ap.monitoring_service.get_session_analysis(
                request_context,
                session_id,
                start_time=start_time,
                end_time=end_time,
                bot_id=quart.request.args.get('botId'),
            )

            # Always return success with the analysis data
            # The frontend will handle the 'found: false' case
            return self.success(data=analysis)

        @self.route(
            '/messages/<message_id>/details',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_message_details(message_id: str, request_context: RequestContext) -> str:
            """Get detailed information for a specific message"""
            details = await self.ap.monitoring_service.get_message_details(request_context, message_id)

            if not details.get('found'):
                return self.http_status(404, 'resource_not_found', 'Message not found')

            return self.success(data=details)

        @self.route('/export', methods=['GET'], permission=Permission.DATA_EXPORT)
        async def export_data(request_context: RequestContext) -> tuple[str, int]:
            """Export monitoring data as CSV"""
            # Parse query parameters
            export_type = quart.request.args.get('type', 'messages')
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100000))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            # Get data based on export type
            if export_type == 'messages':
                data = await self.ap.monitoring_service.export_messages(
                    request_context,
                    bot_ids=bot_ids if bot_ids else None,
                    pipeline_ids=pipeline_ids if pipeline_ids else None,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                headers = [
                    'id',
                    'timestamp',
                    'bot_id',
                    'bot_name',
                    'pipeline_id',
                    'pipeline_name',
                    'runner_name',
                    'message_content',
                    'message_text',
                    'session_id',
                    'status',
                    'level',
                    'platform',
                    'user_id',
                ]
            elif export_type == 'llm-calls':
                data = await self.ap.monitoring_service.export_llm_calls(
                    request_context,
                    bot_ids=bot_ids if bot_ids else None,
                    pipeline_ids=pipeline_ids if pipeline_ids else None,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                headers = [
                    'id',
                    'timestamp',
                    'model_name',
                    'input_tokens',
                    'output_tokens',
                    'total_tokens',
                    'duration_ms',
                    'cost',
                    'status',
                    'bot_id',
                    'bot_name',
                    'pipeline_id',
                    'pipeline_name',
                    'session_id',
                    'message_id',
                    'error_message',
                ]
            elif export_type == 'embedding-calls':
                data = await self.ap.monitoring_service.export_embedding_calls(
                    request_context,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                headers = [
                    'id',
                    'timestamp',
                    'model_name',
                    'prompt_tokens',
                    'total_tokens',
                    'duration_ms',
                    'input_count',
                    'status',
                    'error_message',
                    'knowledge_base_id',
                    'query_text',
                    'session_id',
                    'message_id',
                    'call_type',
                ]
            elif export_type == 'errors':
                data = await self.ap.monitoring_service.export_errors(
                    request_context,
                    bot_ids=bot_ids if bot_ids else None,
                    pipeline_ids=pipeline_ids if pipeline_ids else None,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                headers = [
                    'id',
                    'timestamp',
                    'error_type',
                    'error_message',
                    'bot_id',
                    'bot_name',
                    'pipeline_id',
                    'pipeline_name',
                    'session_id',
                    'message_id',
                    'stack_trace',
                ]
            elif export_type == 'sessions':
                data = await self.ap.monitoring_service.export_sessions(
                    request_context,
                    bot_ids=bot_ids if bot_ids else None,
                    pipeline_ids=pipeline_ids if pipeline_ids else None,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                headers = [
                    'session_id',
                    'bot_id',
                    'bot_name',
                    'pipeline_id',
                    'pipeline_name',
                    'message_count',
                    'start_time',
                    'last_activity',
                    'is_active',
                    'platform',
                    'user_id',
                ]
            elif export_type == 'feedback':
                data = await self.ap.monitoring_service.export_feedback(
                    request_context,
                    bot_ids=bot_ids if bot_ids else None,
                    pipeline_ids=pipeline_ids if pipeline_ids else None,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
                headers = [
                    'id',
                    'timestamp',
                    'feedback_id',
                    'feedback_type',
                    'feedback_content',
                    'inaccurate_reasons',
                    'bot_id',
                    'bot_name',
                    'pipeline_id',
                    'pipeline_name',
                    'session_id',
                    'message_id',
                    'stream_id',
                    'user_id',
                    'platform',
                ]
            else:
                return self.fail(400, f'Invalid export type: {export_type}')

            # Generate CSV content with UTF-8 BOM for Excel compatibility
            import io

            output = io.StringIO()
            # Write UTF-8 BOM for Excel
            output.write('\ufeff')
            # Write header
            output.write(','.join(headers) + '\n')

            # Escape and write each row
            for row in data:
                escaped_values = []
                for header in headers:
                    value = row.get(header, '')
                    escaped_values.append(self.ap.monitoring_service._escape_csv_field(value))
                output.write(','.join(escaped_values) + '\n')

            csv_content = output.getvalue()

            # Return as file download
            response = await quart.make_response(csv_content)
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            response.headers['Content-Disposition'] = (
                f'attachment; filename="monitoring-{export_type}-{int(datetime.datetime.now().timestamp())}.csv"'
            )

            return response, 200

        @self.route('/feedback/stats', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_feedback_stats(request_context: RequestContext) -> str:
            """Get feedback statistics"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            stats = await self.ap.monitoring_service.get_feedback_stats(
                request_context,
                execution_statuses=quart.request.args.getlist('status') or None,
                mode=quart.request.args.get('mode', 'all'),
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
            )

            return self.success(data=stats)

        @self.route('/feedback', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_feedback(request_context: RequestContext) -> str:
            """Get feedback list"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            feedback_type_str = quart.request.args.get('feedbackType')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)
            validate_monitoring_window(start_time, end_time)

            # Parse feedback type
            feedback_type = int(feedback_type_str) if feedback_type_str else None

            feedback_list, total = await self.ap.monitoring_service.get_feedback_list(
                request_context,
                execution_statuses=quart.request.args.getlist('status') or None,
                mode=quart.request.args.get('mode', 'all'),
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                feedback_type=feedback_type,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset,
            )

            return self.success(
                data={
                    'feedback': feedback_list,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            )
