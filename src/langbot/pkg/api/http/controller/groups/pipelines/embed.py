"""Embed widget routes - serve embeddable chat widget for external websites.

All user-facing URLs are keyed by **bot_uuid** (not pipeline_uuid) so that
internal pipeline identifiers are never exposed to end-users.  Each handler
resolves the bot_uuid to the owning ``web_page_bot`` RuntimeBot and extracts
the bound pipeline_uuid for internal routing.
"""

import asyncio
import datetime
import json
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
from ......platform.sources.websocket_manager import ws_connection_manager

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
    # -- helpers -------------------------------------------------------------

    def _resolve_bot(self, bot_uuid: str):
        """Resolve *bot_uuid* to ``(runtime_bot, pipeline_uuid)``.

        Returns ``(None, None)`` when the bot does not exist, is not a
        ``web_page_bot``, is disabled, or has no pipeline bound.
        """
        for bot in self.ap.platform_mgr.bots:
            if (
                bot.bot_entity.uuid == bot_uuid
                and bot.bot_entity.adapter == 'web_page_bot'
                and bot.bot_entity.enable
                and bot.bot_entity.use_pipeline_uuid
            ):
                return bot, bot.bot_entity.use_pipeline_uuid
        return None, None

    def _get_bot_config(self, bot_uuid: str) -> dict:
        for bot in self.ap.platform_mgr.bots:
            if bot.bot_entity.uuid == bot_uuid and bot.bot_entity.adapter == 'web_page_bot':
                return bot.bot_entity.adapter_config
        return {}

    async def _verify_session_token(self, request, bot_uuid: str) -> bool:
        config = self._get_bot_config(bot_uuid)
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

    # -- routes --------------------------------------------------------------

    async def initialize(self) -> None:
        @self.route('/<bot_uuid>/turnstile/verify', methods=['POST'], auth_type=group.AuthType.NONE)
        async def verify_turnstile(bot_uuid: str) -> str:
            if not _is_valid_uuid(bot_uuid):
                return self.http_status(400, -1, 'Invalid bot_uuid format')
            runtime_bot, pipeline_uuid = self._resolve_bot(bot_uuid)
            if runtime_bot is None:
                return self.http_status(404, -1, 'Bot not found or not available')
            try:
                data = await quart.request.get_json()
                token = data.get('token')
                if not token:
                    return self.http_status(400, -1, 'Token is required')

                config = self._get_bot_config(bot_uuid)
                secret = config.get('turnstile_secret_key', '')
                if not secret:
                    ts = time.time()
                    return self.success(data={'token': f'{ts}.dummy'})

                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
                        data={'secret': secret, 'response': token},
                    )
                    result = resp.json()

                if not result.get('success'):
                    return self.http_status(403, -1, 'Turnstile verification failed')

                ts = time.time()
                mac = hmac.new(secret.encode(), f'{ts}'.encode(), hashlib.sha256).hexdigest()
                session_token = f'{ts}.{mac}'

                return self.success(data={'token': session_token})

            except Exception as e:
                logger.error(f'Turnstile verify failed: {e}', exc_info=True)
                return self.http_status(500, -1, 'Internal server error')

        @self.route('/<bot_uuid>/widget.js', methods=['GET'], auth_type=group.AuthType.NONE)
        async def serve_widget(bot_uuid: str) -> quart.Response:
            """Serve the embed widget JavaScript with injected configuration."""
            if not _is_valid_uuid(bot_uuid):
                return self.http_status(400, -1, 'Invalid bot_uuid format')
            runtime_bot, pipeline_uuid = self._resolve_bot(bot_uuid)
            if runtime_bot is None:
                return quart.Response(
                    '// Bot not found or not available', status=404, content_type='application/javascript'
                )
            try:
                template = _get_widget_template()
            except FileNotFoundError:
                return quart.Response('// Widget template not found', status=404, content_type='application/javascript')

            base_url = quart.request.host_url.rstrip('/')
            webhook_prefix = self.ap.instance_config.data.get('api', {}).get('webhook_prefix', '')
            if webhook_prefix:
                base_url = webhook_prefix.rstrip('/')

            if not re.match(r'^https?://[a-zA-Z0-9._:/-]+$', base_url):
                base_url = quart.request.host_url.rstrip('/')

            config = self._get_bot_config(bot_uuid)
            site_key = config.get('turnstile_site_key', '')
            locale = config.get('language', 'en_US') or 'en_US'
            bubble_icon = config.get('bubble_icon', 'logo') or 'logo'
            widget_js = template.replace('__LANGBOT_TURNSTILE_SITE_KEY__', site_key)
            widget_js = widget_js.replace('__LANGBOT_BOT_UUID__', bot_uuid)
            widget_js = widget_js.replace('__LANGBOT_BASE_URL__', base_url)
            widget_js = widget_js.replace('__LANGBOT_LOCALE__', locale)
            widget_js = widget_js.replace('__LANGBOT_BUBBLE_ICON__', bubble_icon)

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

        @self.route('/<bot_uuid>/messages/<session_type>', methods=['GET'], auth_type=group.AuthType.NONE)
        async def get_embed_messages(bot_uuid: str, session_type: str) -> str:
            if not _is_valid_uuid(bot_uuid):
                return self.http_status(400, -1, 'Invalid bot_uuid format')
            runtime_bot, pipeline_uuid = self._resolve_bot(bot_uuid)
            if runtime_bot is None:
                return self.http_status(404, -1, 'Bot not found or not available')
            if not await self._verify_session_token(quart.request, bot_uuid):
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

        @self.route('/<bot_uuid>/reset/<session_type>', methods=['POST'], auth_type=group.AuthType.NONE)
        async def reset_embed_session(bot_uuid: str, session_type: str) -> str:
            if not _is_valid_uuid(bot_uuid):
                return self.http_status(400, -1, 'Invalid bot_uuid format')
            runtime_bot, pipeline_uuid = self._resolve_bot(bot_uuid)
            if runtime_bot is None:
                return self.http_status(404, -1, 'Bot not found or not available')
            if not await self._verify_session_token(quart.request, bot_uuid):
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

        @self.route('/<bot_uuid>/feedback', methods=['POST'], auth_type=group.AuthType.NONE)
        async def submit_feedback(bot_uuid: str) -> str:
            if not _is_valid_uuid(bot_uuid):
                return self.http_status(400, -1, 'Invalid bot_uuid format')
            runtime_bot, pipeline_uuid = self._resolve_bot(bot_uuid)
            if runtime_bot is None:
                return self.http_status(404, -1, 'Bot not found or not available')
            if not await self._verify_session_token(quart.request, bot_uuid):
                return self.http_status(403, -1, 'Unauthorized or session expired')
            try:
                data = await quart.request.get_json()
                message_id = data.get('message_id', '')
                feedback_type = data.get('feedback_type')

                if feedback_type not in (1, 2, 3):
                    return self.http_status(400, -1, 'feedback_type must be 1 (like), 2 (dislike), or 3 (cancel)')

                feedback_id = f'embed_{uuid.uuid4().hex[:12]}'

                await self.ap.monitoring_service.record_feedback(
                    feedback_id=feedback_id,
                    feedback_type=feedback_type,
                    bot_id=runtime_bot.bot_entity.uuid,
                    bot_name=runtime_bot.bot_entity.name or bot_uuid,
                    pipeline_id=pipeline_uuid,
                    message_id=str(message_id),
                    platform='web_page_bot',
                )

                return self.success(data={'feedback_id': feedback_id})

            except Exception as e:
                logger.error(f'Failed to record feedback: {e}', exc_info=True)
                return self.http_status(500, -1, 'Internal server error')

        # -- Embed WebSocket endpoint ----------------------------------------

        @self.quart_app.websocket(self.path + '/<bot_uuid>/ws/connect')
        async def embed_websocket_connect(bot_uuid: str):
            """WebSocket connection for embed widget, keyed by bot_uuid."""
            if not _is_valid_uuid(bot_uuid):
                await quart.websocket.send(json.dumps({'type': 'error', 'message': 'Invalid bot_uuid format'}))
                return

            runtime_bot, pipeline_uuid = self._resolve_bot(bot_uuid)
            if runtime_bot is None:
                await quart.websocket.send(json.dumps({'type': 'error', 'message': 'Bot not found or not available'}))
                return

            session_type = quart.websocket.args.get('session_type', 'person')
            if session_type not in ['person', 'group']:
                await quart.websocket.send(
                    json.dumps({'type': 'error', 'message': 'session_type must be person or group'})
                )
                return

            websocket_adapter = self.ap.platform_mgr.websocket_proxy_bot.adapter
            if not websocket_adapter:
                await quart.websocket.send(json.dumps({'type': 'error', 'message': 'WebSocket adapter not found'}))
                return

            try:
                connection = await ws_connection_manager.add_connection(
                    websocket=quart.websocket._get_current_object(),
                    pipeline_uuid=pipeline_uuid,
                    session_type=session_type,
                    metadata={'user_agent': quart.websocket.headers.get('User-Agent', '')},
                )

                await quart.websocket.send(
                    json.dumps(
                        {
                            'type': 'connected',
                            'connection_id': connection.connection_id,
                            'bot_uuid': bot_uuid,
                            'session_type': session_type,
                            'timestamp': connection.created_at.isoformat(),
                        }
                    )
                )

                logger.debug(
                    f'Embed WebSocket connected: {connection.connection_id} '
                    f'(bot={bot_uuid}, pipeline={pipeline_uuid}, session_type={session_type})'
                )

                receive_task = asyncio.create_task(self._handle_receive(connection, websocket_adapter, runtime_bot))
                send_task = asyncio.create_task(self._handle_send(connection))

                try:
                    await asyncio.gather(receive_task, send_task)
                except Exception as e:
                    logger.error(f'Embed WebSocket task error: {e}')
                finally:
                    await ws_connection_manager.remove_connection(connection.connection_id)

            except Exception as e:
                logger.error(f'Embed WebSocket connection error: {e}', exc_info=True)
                try:
                    await quart.websocket.send(json.dumps({'type': 'error', 'message': 'Internal server error'}))
                except Exception:
                    pass

    # -- WebSocket receive/send helpers --------------------------------------

    async def _handle_receive(self, connection, websocket_adapter, owner_bot):
        try:
            while connection.is_active:
                message = await quart.websocket.receive()
                await ws_connection_manager.update_activity(connection.connection_id)

                try:
                    data = json.loads(message)
                    message_type = data.get('type', 'message')

                    if message_type == 'ping':
                        await connection.send_queue.put(
                            {'type': 'pong', 'timestamp': datetime.datetime.now().isoformat()}
                        )
                    elif message_type == 'message':
                        await websocket_adapter.handle_websocket_message(connection, data, owner_bot=owner_bot)
                    elif message_type == 'disconnect':
                        break

                except json.JSONDecodeError:
                    await connection.send_queue.put({'type': 'error', 'message': 'Invalid JSON format'})

        except Exception as e:
            logger.error(f'Embed receive error: {e}', exc_info=True)
        finally:
            connection.is_active = False

    async def _handle_send(self, connection):
        try:
            while connection.is_active:
                try:
                    message = await asyncio.wait_for(connection.send_queue.get(), timeout=1.0)
                    await quart.websocket.send(json.dumps(message))
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            logger.error(f'Embed send error: {e}', exc_info=True)
        finally:
            connection.is_active = False
