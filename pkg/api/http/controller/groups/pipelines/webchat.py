import quart

from ... import group


@group.group_class('webchat', '/api/v1/pipelines/<pipeline_uuid>/chat')
class WebChatDebugRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/send', methods=['POST'])
        async def send_message(pipeline_uuid: str) -> str:
            """发送调试消息到流水线"""
            try:
                data = await quart.request.get_json()
                session_type = data.get('session_type', 'person')
                message_chain_obj = data.get('message', [])

                if not message_chain_obj:
                    return self.http_status(400, -1, 'message is required')

                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                webchat_adapter = self.ap.platform_mgr.webchat_proxy_bot.adapter

                if not webchat_adapter:
                    return self.http_status(404, -1, 'WebChat adapter not found')

                result = await webchat_adapter.send_debug_message(pipeline_uuid, session_type, message_chain_obj)

                return self.success(data=result)

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/messages/<session_type>', methods=['GET'])
        async def get_messages(session_type: str) -> str:
            """获取调试消息历史"""
            try:
                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                webchat_adapter = None
                for bot in self.ap.platform_mgr.bots:
                    if hasattr(bot.adapter, '__class__') and bot.adapter.__class__.__name__ == 'WebChatAdapter':
                        webchat_adapter = bot.adapter
                        break

                if not webchat_adapter:
                    return self.http_status(404, -1, 'WebChat adapter not found')

                messages = webchat_adapter.get_debug_messages(session_type)

                return self.success(data={'messages': messages})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/reset/<session_type>', methods=['POST'])
        async def reset_session(session_type: str) -> str:
            """重置调试会话"""
            try:
                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                webchat_adapter = None
                for bot in self.ap.platform_mgr.bots:
                    if hasattr(bot.adapter, '__class__') and bot.adapter.__class__.__name__ == 'WebChatAdapter':
                        webchat_adapter = bot.adapter
                        break

                if not webchat_adapter:
                    return self.http_status(404, -1, 'WebChat adapter not found')

                webchat_adapter.reset_debug_session(session_type)

                return self.success(data={'message': 'Session reset successfully'})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/pipelines', methods=['GET'])
        async def get_pipelines() -> str:
            """获取可用的流水线列表"""
            try:
                pipelines = await self.ap.pipeline_mgr.get_pipelines()

                pipeline_list = []
                for pipeline in pipelines:
                    pipeline_list.append(
                        {
                            'id': pipeline.uuid,
                            'name': pipeline.name,
                            'description': pipeline.description,
                            'is_default': pipeline.is_default,
                        }
                    )

                return self.success(data={'pipelines': pipeline_list})

            except Exception as e:
                return self.http_status(500, -1, f'Internal server error: {str(e)}')
