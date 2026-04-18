"""Embed widget routes - serve embeddable chat widget for external websites"""

import logging
import uuid

import quart

from ... import group
from ......utils import paths

logger = logging.getLogger(__name__)

# Cache the widget template content
_widget_template_cache: str | None = None
_logo_bytes_cache: bytes | None = None


def _get_widget_template() -> str:
    """Load and cache the widget JS template."""
    global _widget_template_cache
    if _widget_template_cache is None:
        template_path = paths.get_resource_path('templates/embed/widget.js')
        with open(template_path, 'r', encoding='utf-8') as f:
            _widget_template_cache = f.read()
    return _widget_template_cache


def _get_logo_bytes() -> bytes:
    """Load and cache the logo image."""
    global _logo_bytes_cache
    if _logo_bytes_cache is None:
        logo_path = paths.get_resource_path('templates/embed/logo.webp')
        with open(logo_path, 'rb') as f:
            _logo_bytes_cache = f.read()
    return _logo_bytes_cache


@group.group_class('embed', '/api/v1/embed')
class EmbedRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/<pipeline_uuid>/widget.js', methods=['GET'], auth_type=group.AuthType.NONE)
        async def serve_widget(pipeline_uuid: str) -> quart.Response:
            """Serve the embed widget JavaScript with injected configuration."""
            try:
                template = _get_widget_template()
            except FileNotFoundError:
                return quart.Response('// Widget template not found', status=404, content_type='application/javascript')

            # Determine base URL from request or config
            base_url = quart.request.host_url.rstrip('/')
            webhook_prefix = self.ap.instance_config.data.get('api', {}).get('webhook_prefix', '')
            if webhook_prefix:
                base_url = webhook_prefix.rstrip('/')

            # Inject configuration
            widget_js = template.replace('__LANGBOT_PIPELINE_UUID__', pipeline_uuid)
            widget_js = widget_js.replace('__LANGBOT_BASE_URL__', base_url)

            response = quart.Response(widget_js, content_type='application/javascript; charset=utf-8')
            response.headers['Cache-Control'] = 'public, max-age=300'
            return response

        @self.route('/logo', methods=['GET'], auth_type=group.AuthType.NONE)
        async def serve_logo() -> quart.Response:
            """Serve the LangBot logo for the embed widget."""
            try:
                logo_data = _get_logo_bytes()
            except FileNotFoundError:
                return quart.Response('', status=404)

            response = quart.Response(logo_data, content_type='image/webp')
            response.headers['Cache-Control'] = 'public, max-age=86400'
            return response

        @self.route('/<pipeline_uuid>/messages/<session_type>', methods=['GET'], auth_type=group.AuthType.NONE)
        async def get_embed_messages(pipeline_uuid: str, session_type: str) -> str:
            """Get message history for embed widget (no auth required)."""
            try:
                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter

                if not websocket_adapter:
                    return self.http_status(404, -1, 'WebSocket adapter not found')

                messages = websocket_adapter.get_websocket_messages(pipeline_uuid, session_type)

                return self.success(data={'messages': messages})

            except Exception as e:
                logger.error(f'Failed to get embed messages: {e}', exc_info=True)
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/<pipeline_uuid>/reset/<session_type>', methods=['POST'], auth_type=group.AuthType.NONE)
        async def reset_embed_session(pipeline_uuid: str, session_type: str) -> str:
            """Reset session for embed widget (no auth required)."""
            try:
                if session_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'session_type must be person or group')

                websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter

                if not websocket_adapter:
                    return self.http_status(404, -1, 'WebSocket adapter not found')

                websocket_adapter.reset_session(pipeline_uuid, session_type)

                return self.success(data={'message': 'Session reset successfully'})

            except Exception as e:
                logger.error(f'Failed to reset embed session: {e}', exc_info=True)
                return self.http_status(500, -1, f'Internal server error: {str(e)}')

        @self.route('/<pipeline_uuid>/feedback', methods=['POST'], auth_type=group.AuthType.NONE)
        async def submit_feedback(pipeline_uuid: str) -> str:
            """Record user feedback (like/dislike) from embed widget."""
            try:
                data = await quart.request.get_json()
                message_id = data.get('message_id', '')
                feedback_type = data.get('feedback_type')  # 1=like, 2=dislike, 3=cancel

                if feedback_type not in (1, 2, 3):
                    return self.http_status(400, -1, 'feedback_type must be 1 (like), 2 (dislike), or 3 (cancel)')

                # Find the owning bot for this pipeline
                bot_id = 'websocket-proxy-bot'
                bot_name = 'WebSocket'
                for bot in self.ap.platform_mgr.bots:
                    if bot.bot_entity.adapter == 'web_page_bot' and bot.bot_entity.use_pipeline_uuid == pipeline_uuid:
                        bot_id = bot.bot_entity.uuid
                        bot_name = bot.bot_entity.name or bot_id
                        break

                feedback_id = f'embed_{uuid.uuid4().hex[:12]}'

                await self.ap.monitoring_service.record_feedback(
                    feedback_id=feedback_id,
                    feedback_type=feedback_type,
                    bot_id=bot_id,
                    bot_name=bot_name,
                    pipeline_id=pipeline_uuid,
                    message_id=str(message_id),
                    platform='web_page_bot',
                )

                return self.success(data={'feedback_id': feedback_id})

            except Exception as e:
                logger.error(f'Failed to record feedback: {e}', exc_info=True)
                return self.http_status(500, -1, f'Internal server error: {str(e)}')
