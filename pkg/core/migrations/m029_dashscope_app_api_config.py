from __future__ import annotations

from .. import migration


@migration.migration_class('dashscope-app-api-config', 29)
class DashscopeAppAPICfgMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'dashscope-app-api' not in self.ap.provider_cfg.data

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['dashscope-app-api'] = {
            'app-type': 'agent',
            'api-key': 'sk-1234567890',
            'agent': {'app-id': 'Your_app_id', 'references_quote': '参考资料来自:'},
            'workflow': {
                'app-id': 'Your_app_id',
                'references_quote': '参考资料来自:',
                'biz_params': {'city': '北京', 'date': '2023-08-10'},
            },
        }

        await self.ap.provider_cfg.dump_config()
