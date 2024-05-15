from __future__ import annotations

from .. import migration


@migration.migration_class("vision-and-oss-config", 6)
class VisionAndOSSConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return "enable-vision" not in self.ap.provider_cfg.data \
            or "oss" not in self.ap.system_cfg.data

    async def run(self):
        """执行迁移"""
        if "enable-vision" not in self.ap.provider_cfg.data:
            self.ap.provider_cfg.data["enable-vision"] = False

        if "oss" not in self.ap.system_cfg.data:
            self.ap.system_cfg.data["oss"] = [
                {
                    "type": "aliyun",
                    "endpoint": "https://oss-cn-hangzhou.aliyuncs.com",
                    "public-read-base-url": "https://qchatgpt.oss-cn-hangzhou.aliyuncs.com",
                    "access-key-id": "LTAI5tJ5Q5J8J6J5J5J5J5J5",
                    "access-key-secret": "xxxxxx",
                    "bucket": "qchatgpt",
                    "prefix": "qchatgpt",
                    "enable": False,
                }
            ]

        await self.ap.provider_cfg.dump_config()
        await self.ap.system_cfg.dump_config()
