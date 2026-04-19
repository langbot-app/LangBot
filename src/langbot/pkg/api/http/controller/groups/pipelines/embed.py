"""Embed widget routes - serve embeddable chat widget for external websites"""

import logging
import uuid
import hmac
import hashlib
import time
import re
import httpx

import quart

from ... import group
from ......utils import paths

logger = logging.getLogger(__name__)

# Cache the widget template content
_widget_template_cache: str | None = None
_logo_bytes_cache: bytes | None = None


def _is_valid_uuid(s: str) -> bool:
    return bool(re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', s))


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
    def _get_bot_config(self, pipeline_uuid: str) -> dict:
        for bot in self.ap.platform_mgr.bots:
            if bot.bot_entity.adapter == 'web_page_bot' and bot.bot_entity.use_pipeline_uuid == pipeline_uuid:
                return bot.bot_entity.adapter_config
        return {}

    async def _verify_session_token(self, request, pipeline_uuid: str) -> bool:
        config = self._get_bot_config(pipeline_uuid)
        secret = config.get('turnstile_secret_key', '')
        if not secret:
            return True
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return False
        token = auth_header[7:]
        try:
            ts_str, mac = token.split('.', 1)
            ts = float(ts_str)
            if time.time() - ts > 86400:
                return False
            expected_mac = hmac.new(secret.encode(), f'{ts_str}'.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(mac, expected_mac)
        except Exception:
            return False

    async def initialize(self) -> None:
        @self.route('/<pipeline_uuid>/turnstile/verify', methods=['POST'], auth_type=group.AuthType.NONE)
        async def verify_turnstile(pipeline_uuid: str) -> str:
            if not _is_valid_uuid(pipeline_uuid):
                return self.http_status(400, -1, 'Invalid pipeline_uuid format')
            try:
                data = await quart.request.get_json()
                token = data.get('token')
                if not token:
                    return self.http_status(400, -1, 'Token is required')

                config = self._get_bot_config(pipeline_uuid)
                secret = config.get('turnstile_secret_key', '')
                if not secret:
                    # If not configured, just return a dummy token
                    ts = time.time()
                    return self.success(data={'token': f'{ts}.dummy'})

                # Verify with Cloudflare
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
                        data={'secret': secret, 'response': token},
                    )
                    result = resp.json()

                if not result.get('success'):
                    return self.http_status(403, -1, 'Turnstile verification failed')

                # Sign token
                ts = time.time()
                mac = hmac.new(secret.encode(), f'{ts}'.encode(), hashlib.sha256).hexdigest()
                session_token = f'{ts}.{mac}'

                return self.success(data={'token': session_token})

            except Exception as e:
                logger.error(f'Turnstile verify failed: {e}', exc_info=True)
                return self.http_status(500, -1, 'Internal server error')

        @self.route('/<pipeline_uuid>/widget.js', methods=['GET'], auth_type=group.AuthType.NONE)
        async def serve_widget(pipeline_uuid: str) -> quart.Response:
            """Serve the embed widget JavaScript with injected configuration."""
            if not _is_valid_uuid(pipeline_uuid):
                return self.http_status(400, -1, 'Invalid pipeline_uuid format')
            try:
                template = _get_widget_template()
            except FileNotFoundError:
                return quart.Response('// Widget template not found', status=404, content_type='application/javascript')

            # Determine base URL from request or config
            base_url = quart.request.host_url.rstrip('/')
            webhook_prefix = self.ap.instance_config.data.get('api', {}).get('webhook_prefix', '')
            if webhook_prefix:
                base_url = webhook_prefix.rstrip('/')

            # Sanitize base URL
            if not re.match(r'^https?://[a-zA-Z0-9._:/-]+$', base_url):
                base_url = quart.request.host_url.rstrip('/')
            # Inject configuration
            config = self._get_bot_config(pipeline_uuid)
            site_key = config.get('turnstile_site_key', '')
            widget_js = template.replace('__LANGBOT_TURNSTILE_SITE_KEY__', site_key)
            widget_js = widget_js.replace('__LANGBOT_PIPELINE_UUID__', pipeline_uuid)

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
            if not _is_valid_uuid(pipeline_uuid):
                return self.http_status(400, -1, 'Invalid pipeline_uuid format')
            if not await self._verify_session_token(quart.request, pipeline_uuid):
                return self.http_status(403, -1, 'Unauthorized or session expired')
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
                return self.http_status(500, -1, 'Internal server error')

        @self.route('/<pipeline_uuid>/reset/<session_type>', methods=['POST'], auth_type=group.AuthType.NONE)
        async def reset_embed_session(pipeline_uuid: str, session_type: str) -> str:
            """Reset session for embed widget (no auth required)."""
            if not _is_valid_uuid(pipeline_uuid):
                return self.http_status(400, -1, 'Invalid pipeline_uuid format')
            if not await self._verify_session_token(quart.request, pipeline_uuid):
                return self.http_status(403, -1, 'Unauthorized or session expired')
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
                return self.http_status(500, -1, 'Internal server error')

        @self.route('/<pipeline_uuid>/feedback', methods=['POST'], auth_type=group.AuthType.NONE)
        async def submit_feedback(pipeline_uuid: str) -> str:
            """Record user feedback (like/dislike) from embed widget."""
            if not _is_valid_uuid(pipeline_uuid):
                return self.http_status(400, -1, 'Invalid pipeline_uuid format')
            if not await self._verify_session_token(quart.request, pipeline_uuid):
                return self.http_status(403, -1, 'Unauthorized or session expired')
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
                return self.http_status(500, -1, 'Internal server error')
