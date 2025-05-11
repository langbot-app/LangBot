from __future__ import annotations

from .. import migration


@migration.migration_class('openai-config-migration', 2)
class OpenAIConfigMigration(migration.Migration):
    """OpenAI配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'openai-config' in self.ap.provider_cfg.data

    async def run(self):
        """执行迁移"""
        old_openai_config = self.ap.provider_cfg.data['openai-config'].copy()

        if 'keys' not in self.ap.provider_cfg.data:
            self.ap.provider_cfg.data['keys'] = {}

        if 'openai' not in self.ap.provider_cfg.data['keys']:
            self.ap.provider_cfg.data['keys']['openai'] = []

        self.ap.provider_cfg.data['keys']['openai'] = old_openai_config['api-keys']

        self.ap.provider_cfg.data['model'] = old_openai_config['chat-completions-params']['model']

        del old_openai_config['chat-completions-params']['model']

        if 'requester' not in self.ap.provider_cfg.data:
            self.ap.provider_cfg.data['requester'] = {}

        if 'openai-chat-completions' not in self.ap.provider_cfg.data['requester']:
            self.ap.provider_cfg.data['requester']['openai-chat-completions'] = {}

        self.ap.provider_cfg.data['requester']['openai-chat-completions'] = {
            'base-url': old_openai_config['base_url'],
            'args': old_openai_config['chat-completions-params'],
            'timeout': old_openai_config['request-timeout'],
        }

        del self.ap.provider_cfg.data['openai-config']

        await self.ap.provider_cfg.dump_config()
