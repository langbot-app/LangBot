from __future__ import annotations

import datetime
import quart

from .. import group


@group.group_class('monitoring', '/api/v1/monitoring')
class MonitoringRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/overview', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_overview() -> str:
            """Get overview metrics"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')

            # Parse datetime
            start_time = datetime.datetime.fromisoformat(start_time_str) if start_time_str else None
            end_time = datetime.datetime.fromisoformat(end_time_str) if end_time_str else None

            metrics = await self.ap.monitoring_service.get_overview_metrics(
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
            )

            return self.success(data=metrics)

        @self.route('/messages', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_messages() -> str:
            """Get message logs"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = datetime.datetime.fromisoformat(start_time_str) if start_time_str else None
            end_time = datetime.datetime.fromisoformat(end_time_str) if end_time_str else None

            messages, total = await self.ap.monitoring_service.get_messages(
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
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

        @self.route('/llm-calls', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_llm_calls() -> str:
            """Get LLM call records"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = datetime.datetime.fromisoformat(start_time_str) if start_time_str else None
            end_time = datetime.datetime.fromisoformat(end_time_str) if end_time_str else None

            llm_calls, total = await self.ap.monitoring_service.get_llm_calls(
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

        @self.route('/sessions', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_sessions() -> str:
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
            start_time = datetime.datetime.fromisoformat(start_time_str) if start_time_str else None
            end_time = datetime.datetime.fromisoformat(end_time_str) if end_time_str else None

            # Parse is_active
            is_active = None
            if is_active_str:
                is_active = is_active_str.lower() == 'true'

            sessions, total = await self.ap.monitoring_service.get_sessions(
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

        @self.route('/errors', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_errors() -> str:
            """Get error logs"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            # Parse datetime
            start_time = datetime.datetime.fromisoformat(start_time_str) if start_time_str else None
            end_time = datetime.datetime.fromisoformat(end_time_str) if end_time_str else None

            errors, total = await self.ap.monitoring_service.get_errors(
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

        @self.route('/data', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_all_data() -> str:
            """Get all monitoring data in a single request"""
            # Parse query parameters
            bot_ids = quart.request.args.getlist('botId')
            pipeline_ids = quart.request.args.getlist('pipelineId')
            start_time_str = quart.request.args.get('startTime')
            end_time_str = quart.request.args.get('endTime')
            limit = int(quart.request.args.get('limit', 50))

            # Parse datetime
            start_time = datetime.datetime.fromisoformat(start_time_str) if start_time_str else None
            end_time = datetime.datetime.fromisoformat(end_time_str) if end_time_str else None

            # Get overview metrics
            overview = await self.ap.monitoring_service.get_overview_metrics(
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
            )

            # Get messages
            messages, messages_total = await self.ap.monitoring_service.get_messages(
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=0,
            )

            # Get LLM calls
            llm_calls, llm_calls_total = await self.ap.monitoring_service.get_llm_calls(
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=0,
            )

            # Get sessions
            sessions, sessions_total = await self.ap.monitoring_service.get_sessions(
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
                bot_ids=bot_ids if bot_ids else None,
                pipeline_ids=pipeline_ids if pipeline_ids else None,
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
                    'sessions': sessions,
                    'errors': errors,
                    'totalCount': {
                        'messages': messages_total,
                        'llmCalls': llm_calls_total,
                        'sessions': sessions_total,
                        'errors': errors_total,
                    },
                }
            )
