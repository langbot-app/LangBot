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
            self.ap.logger.debug(f'[webhook] 收到请求: bot_uuid={bot_uuid}, path={path}, method={quart.request.method}')

            runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)

            if not runtime_bot:
                self.ap.logger.warning(f'[webhook] Bot未找到: bot_uuid={bot_uuid}')
                return quart.jsonify({'error': 'Bot not found'}), 404

            if not runtime_bot.enable:
                self.ap.logger.warning(f'[webhook] Bot已禁用: bot_uuid={bot_uuid}')
                return quart.jsonify({'error': 'Bot is disabled'}), 403

            if not hasattr(runtime_bot.adapter, 'handle_unified_webhook'):
                self.ap.logger.warning(f'[webhook] Adapter不支持unified_webhook: bot_uuid={bot_uuid}')
                return quart.jsonify({'error': 'Adapter does not support unified webhook'}), 501

            adapter_bot = getattr(runtime_bot.adapter, 'bot', None)
            adapter_corpid = getattr(adapter_bot, 'corpid', '') if adapter_bot else ''
            adapter_corpid_short = adapter_corpid[:10] if adapter_corpid else 'N/A'
            adapter_token_cache = getattr(adapter_bot, 'token_cache', None)
            adapter_secret_fp = getattr(adapter_token_cache, 'secret_fingerprint', '') if adapter_token_cache else ''
            adapter_secret_fp_short = adapter_secret_fp[:8] if adapter_secret_fp else 'N/A'
            self.ap.logger.debug(
                f'[webhook] 分发到adapter: bot_uuid={bot_uuid}, adapter={type(runtime_bot.adapter).__name__}, corpid={adapter_corpid_short}, secret_fp={adapter_secret_fp_short}'
            )

            response = await runtime_bot.adapter.handle_unified_webhook(
                bot_uuid=bot_uuid,
                path=path,
                request=quart.request,
            )

            self.ap.logger.debug(f'[webhook] adapter响应完成: bot_uuid={bot_uuid}')
            return response

        except Exception as e:
            self.ap.logger.error(f'Webhook dispatch error for bot {bot_uuid}: {traceback.format_exc()}')
            return quart.jsonify({'error': str(e)}), 500
