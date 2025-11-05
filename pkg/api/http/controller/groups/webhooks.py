"""统一 Webhook 路由组

处理所有外部平台的回调请求，统一在一个端口上通过 bot_uuid 路由到对应的适配器。

路由格式：
- /bots/{bot_uuid} - 处理 bot 的 webhook 回调
- /bots/{bot_uuid}/{path} - 处理带子路径的 webhook 回调

Example:
    http://your-server.com:5300/bots/550e8400-e29b-41d4-a716-446655440000
"""

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
            # 通过 UUID 获取运行时 bot
            runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)

            if not runtime_bot:
                return quart.jsonify({'error': 'Bot not found'}), 404

            if not runtime_bot.enable:
                return quart.jsonify({'error': 'Bot is disabled'}), 403

            # 检查 adapter 是否支持统一 webhook
            if not hasattr(runtime_bot.adapter, 'handle_unified_webhook'):
                return quart.jsonify({'error': 'Adapter does not support unified webhook'}), 501

            # 调用 adapter 的 handle_unified_webhook 方法，显式传递 request 对象
            response = await runtime_bot.adapter.handle_unified_webhook(
                bot_uuid=bot_uuid,
                path=path,
                request=quart.request,
            )

            return response

        except Exception as e:
            self.ap.logger.error(f'Webhook dispatch error for bot {bot_uuid}: {traceback.format_exc()}')
            return quart.jsonify({'error': str(e)}), 500
