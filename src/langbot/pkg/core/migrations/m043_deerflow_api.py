from __future__ import annotations

from .. import migration


@migration.migration_class('deerflow-api-config', 43)
class DeerFlowAPICfgMigration(migration.Migration):
    """DeerFlow API 配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'deerflow-api' not in self.ap.provider_cfg.data

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['deerflow-api'] = {
            'api-base': 'http://127.0.0.1:2026',
            'api-key': '',
            'auth-header': '',
            'assistant-id': 'lead_agent',
            'model-name': '',
            'thinking-enabled': False,
            'plan-mode': False,
            'subagent-enabled': False,
            'max-concurrent-subagents': 3,
            'timeout': 300,
            'recursion-limit': 1000,
        }

        await self.ap.provider_cfg.dump_config()
