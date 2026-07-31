from __future__ import annotations

import datetime
import quart

from ...authz import Permission
from ...context import RequestContext
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

            metrics = await self.ap.monitoring_service.get_overview_metrics(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
            )

            return self.success(data=metrics)

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

            stats = await self.ap.monitoring_service.get_token_statistics(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                bucket=bucket,
            )

            return self.success(data=stats)

        @self.route('/messages', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_messages(request_context: RequestContext) -> str:
            """Get message logs"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            session_ids = quart.request.args.getlist('sessionId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)

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

        @self.route('/llm-calls', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_llm_calls(request_context: RequestContext) -> str:
            """Get LLM call records"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)

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

        @self.route('/tool-calls', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_tool_calls(request_context: RequestContext) -> str:
            """Get tool call records"""
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            session_ids = quart.request.args.getlist('sessionId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)

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

        @self.route('/embedding-calls', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_embedding_calls(request_context: RequestContext) -> str:
            """Get embedding call records"""
            # Parse query parameters
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            knowledge_base_id = quart.request.args.get('knowledgeBaseId')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)

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

        @self.route('/sessions', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_sessions(request_context: RequestContext) -> str:
            """Get session information"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            is_active_str = quart.request.args.get('isActive')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)

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

        @self.route('/errors', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_errors(request_context: RequestContext) -> str:
            """Get error logs"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)

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
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 50))

            # Parse datetime
            start_time = parse_iso_datetime(start_time_str)
            end_time = parse_iso_datetime(end_time_str)

            # Get overview metrics
            overview = await self.ap.monitoring_service.get_overview_metrics(
                request_context,
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
            )

            # Get messages
            messages, messages_total = await self.ap.monitoring_service.get_messages(
                request_context,
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
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=0,
            )

            return self.success(
                data={
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

        @self.route('/sessions/<session_id>/analysis', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_session_analysis(session_id: str, request_context: RequestContext) -> str:
            """Get detailed analysis for a specific session"""
            analysis = await self.ap.monitoring_service.get_session_analysis(request_context, session_id)

            # Always return success with the analysis data
            # The frontend will handle the 'found: false' case
            return self.success(data=analysis)

        @self.route('/messages/<message_id>/details', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_message_details(message_id: str, request_context: RequestContext) -> str:
            """Get detailed information for a specific message"""
            details = await self.ap.monitoring_service.get_message_details(request_context, message_id)

            if not details.get('found'):
                return self.error(message=f'Message {message_id} not found', code=404)

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
                return self.error(message=f'Invalid export type: {export_type}', code=400)

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

            stats = await self.ap.monitoring_service.get_feedback_stats(
                request_context,
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

            # Parse feedback type
            feedback_type = int(feedback_type_str) if feedback_type_str else None

            feedback_list, total = await self.ap.monitoring_service.get_feedback_list(
                request_context,
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
