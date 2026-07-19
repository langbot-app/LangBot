from __future__ import annotations

import quart
import traceback

from .. import group


@group.group_class('webhooks', '/bots')
class WebhookRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/<bot_uuid>', methods=['GET', 'POST'], auth_type=group.AuthType.NONE)
        async def handle_webhook(bot_uuid: str):
            """处理 bot webhook 回调（无子路径）"""
            return await self._dispatch_webhook(bot_uuid, '')

        @self.route('/<bot_uuid>/<path:path>', methods=['GET', 'POST'], auth_type=group.AuthType.NONE)
        async def handle_webhook_with_path(bot_uuid: str, path: str):
            """处理 bot webhook 回调（带子路径）"""
            return await self._dispatch_webhook(bot_uuid, path)

    async def _dispatch_webhook(self, bot_uuid: str, path: str):
        """分发 webhook 请求到对应的 bot adapter

        Args:
            bot_uuid: Bot 的 UUID
            path: 子路径（如果有的话）

        Returns:
            适配器返回的响应
        """
        try:
            # Public ingress never accepts X-Workspace-Id.  The opaque bot UUID
            # is resolved against the already-bound runtime resource, which
            # carries the trusted Workspace and placement generation.
            runtime_bot = await self.ap.platform_mgr.resolve_public_bot(bot_uuid)

            if not runtime_bot:
                return quart.jsonify({'error': 'Bot not found'}), 404

            if not runtime_bot.enable:
                return quart.jsonify({'error': 'Bot is disabled'}), 403

            if not hasattr(runtime_bot.adapter, 'handle_unified_webhook'):
                return quart.jsonify({'error': 'Adapter does not support unified webhook'}), 501

            async def dispatch():
                await self.ap.workspace_service.get_execution_binding(
                    runtime_bot.workspace_uuid,
                    expected_generation=runtime_bot.placement_generation,
                )
                return await runtime_bot.adapter.handle_unified_webhook(
                    bot_uuid=bot_uuid,
                    path=path,
                    request=quart.request,
                )

            persistence_mgr = self.ap.persistence_mgr
            cloud_runtime = getattr(getattr(persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime'
            if cloud_runtime:
                tenant_scope = getattr(persistence_mgr, 'tenant_scope', None)
                if not callable(tenant_scope):
                    raise RuntimeError('Cloud webhook dispatch requires an explicit tenant scope')
                async with tenant_scope(runtime_bot.workspace_uuid):
                    response = await dispatch()
            else:
                response = await dispatch()

            return response

        except Exception:
            request_id = self.request_id()
            self.ap.logger.error(
                f'Webhook dispatch error request_id={request_id} bot={bot_uuid}: {traceback.format_exc()}'
            )
            return self.internal_error_response(request_id)
