from __future__ import annotations

from .. import migration


@migration.migration_class('qiniu-config', 42)
class QiniuConfigMigration(migration.Migration):
    """Qiniu 配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return (
            'qiniu-chat-completions' not in self.ap.provider_cfg.data['requester']
            or 'qiniu' not in self.ap.provider_cfg.data['keys']
        )

    async def run(self):
        """执行迁移"""
        if 'qiniu-chat-completions' not in self.ap.provider_cfg.data['requester']:
            self.ap.provider_cfg.data['requester']['qiniu-chat-completions'] = {
                'base-url': 'https://api.qnaigc.com/v1',
                'args': {},
                'timeout': 120,
            }

        if 'qiniu' not in self.ap.provider_cfg.data['keys']:
            self.ap.provider_cfg.data['keys']['qiniu'] = []

        await self.ap.provider_cfg.dump_config()
