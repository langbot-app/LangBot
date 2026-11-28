from __future__ import annotations

import base64
import re

import quart
from langbot_plugin.entities.io.errors import ActionCallTimeoutError

from .. import group

# Largest request body forwarded to a plugin Webhook component. Mirrors
# ``langbot_plugin.api.definition.components.webhook.WEBHOOK_MAX_BODY_BYTES``.
MAX_WEBHOOK_BODY_BYTES = 1024 * 1024

_WEBHOOK_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,128}$')
_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
# Headers never forwarded to plugin code: browser session state and hop-by-hop
# transport details carry no meaning for a webhook handler.
_DROPPED_REQUEST_HEADERS = frozenset({'cookie', 'connection', 'keep-alive', 'transfer-encoding', 'upgrade'})
_DROPPED_RESPONSE_HEADERS = frozenset(
    {'set-cookie', 'connection', 'keep-alive', 'transfer-encoding', 'upgrade', 'content-length'}
)

_ERROR_STATUS = {
    'plugin_disabled': 403,
    'plugin_runtime_unavailable': 503,
    'plugin_not_connected': 503,
    'webhook_not_initialized': 503,
    'webhook_handler_failed': 502,
}


@group.group_class('plugin_webhooks', '/plugins/webhooks')
class PluginWebhookRouterGroup(group.RouterGroup):
    """Public ingress for plugin ``Webhook`` components.

    ``/plugins/webhooks/<installation_uuid>/<webhook_name>[/<path>]`` mirrors
    the Bot webhook pattern (``/bots/<bot_uuid>``): the opaque installation
    UUID is the routing key and the plugin authenticates its caller.
    """

    async def initialize(self) -> None:
        @self.route('/<installation_uuid>/<webhook_name>', methods=_METHODS, auth_type=group.AuthType.NONE)
        async def _(installation_uuid: str, webhook_name: str):
            return await self._dispatch(installation_uuid, webhook_name, '')

        @self.route(
            '/<installation_uuid>/<webhook_name>/<path:sub_path>',
            methods=_METHODS,
            auth_type=group.AuthType.NONE,
        )
        async def _(installation_uuid: str, webhook_name: str, sub_path: str):
            return await self._dispatch(installation_uuid, webhook_name, '/' + sub_path)

    async def _dispatch(self, installation_uuid: str, webhook_name: str, sub_path: str):
        if not _WEBHOOK_NAME.match(webhook_name):
            return quart.jsonify({'error': 'Webhook not found'}), 404

        request = quart.request
        if request.content_length is not None and request.content_length > MAX_WEBHOOK_BODY_BYTES:
            return quart.jsonify({'error': 'Request body too large'}), 413
        body = b''
        async for chunk in request.body:
            body += chunk
            if len(body) > MAX_WEBHOOK_BODY_BYTES:
                return quart.jsonify({'error': 'Request body too large'}), 413

        payload = {
            'method': request.method.upper(),
            'path': sub_path,
            'query': {key: value for key, value in request.args.items()},
            'headers': {
                key.lower(): value
                for key, value in request.headers.items()
                if key.lower() not in _DROPPED_REQUEST_HEADERS
            },
            'body_base64': base64.b64encode(body).decode('ascii'),
            'remote_addr': request.remote_addr,
        }

        try:
            result = await self.ap.plugin_connector.handle_public_webhook(installation_uuid, webhook_name, payload)
        except (ActionCallTimeoutError, TimeoutError):
            return quart.jsonify({'error': 'Plugin webhook timed out'}), 504
        except Exception as exc:
            self.ap.logger.warning(
                'Plugin webhook %s/%s failed: %s: %s',
                installation_uuid,
                webhook_name,
                type(exc).__name__,
                exc,
            )
            return quart.jsonify({'error': 'Plugin webhook failed'}), 502

        if result is None:
            return quart.jsonify({'error': 'Webhook not found'}), 404
        error = result.get('error')
        if error:
            if error in ('webhook_not_found', 'plugin_not_found'):
                return quart.jsonify({'error': 'Webhook not found'}), 404
            return quart.jsonify({'error': str(error)}), _ERROR_STATUS.get(str(error), 502)

        response = result.get('response') or {}
        try:
            status = int(response.get('status', 200))
            raw = response.get('body_base64') or ''
            response_body = base64.b64decode(raw) if raw else b''
        except (TypeError, ValueError):
            return quart.jsonify({'error': 'Invalid plugin webhook response'}), 502
        if not 100 <= status <= 599:
            return quart.jsonify({'error': 'Invalid plugin webhook response'}), 502
        headers = {
            str(key): str(value)
            for key, value in (response.get('headers') or {}).items()
            if str(key).lower() not in _DROPPED_RESPONSE_HEADERS
        }
        return quart.Response(response_body, status=status, headers=headers)
