from __future__ import annotations

from .. import migration


@migration.migration_class('weknora-api-config', 42)
class WeKnoraAPICfgMigration(migration.Migration):
    """WeKnora API 配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'weknora-api' not in self.ap.provider_cfg.data

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['weknora-api'] = {
            'base-url': 'http://localhost:8080/api/v1',
            'app-type': 'agent',
            'api-key': '',
            'agent-id': 'builtin-smart-reasoning',
            'knowledge-base-ids': [],
            'web-search-enabled': False,
            'timeout': 120,
            'base-prompt': '请回答用户的问题。',
        }

        await self.ap.provider_cfg.dump_config()
