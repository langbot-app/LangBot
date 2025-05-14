from __future__ import annotations

import os

from .. import migration


@migration.migration_class('sensitive-word-migration', 1)
class SensitiveWordMigration(migration.Migration):
    """敏感词迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return os.path.exists('data/config/sensitive-words.json') and not os.path.exists(
            'data/metadata/sensitive-words.json'
        )

    async def run(self):
        """执行迁移"""
        # 移动文件
        os.rename('data/config/sensitive-words.json', 'data/metadata/sensitive-words.json')

        # 重新加载配置
        await self.ap.sensitive_meta.load_config()
