from __future__ import annotations

import secrets

from .. import stage, app
from ..bootutils import config
from ...config import settings as settings_mgr
from ...utils import schema


@stage.stage_class("LoadConfigStage")
class LoadConfigStage(stage.BootingStage):
    """加载配置文件阶段
    """

    async def run(self, ap: app.Application):
        """启动
        """
        
        ap.settings_mgr = settings_mgr.SettingsManager(ap)
        await ap.settings_mgr.initialize()

        ap.command_cfg = await config.load_json_config("data/config/command.json", "templates/command.json", completion=False)
        ap.pipeline_cfg = await config.load_json_config("data/config/pipeline.json", "templates/pipeline.json", completion=False)
        ap.platform_cfg = await config.load_json_config("data/config/platform.json", "templates/platform.json", completion=False)
        ap.provider_cfg = await config.load_json_config("data/config/provider.json", "templates/provider.json", completion=False)
        ap.system_cfg = await config.load_json_config("data/config/system.json", "templates/system.json", completion=False)

        ap.settings_mgr.register_manager(
            name="command.json",
            description="命令配置",
            manager=ap.command_cfg,
            schema=schema.CONFIG_COMMAND_SCHEMA,
            doc_link="https://docs.langbot.app/config/function/command.html"
        )

        ap.settings_mgr.register_manager(
            name="pipeline.json",
            description="消息处理流水线配置",
            manager=ap.pipeline_cfg,
            schema=schema.CONFIG_PIPELINE_SCHEMA,
            doc_link="https://docs.langbot.app/config/function/pipeline.html"
        )

        ap.settings_mgr.register_manager(
            name="platform.json",
            description="消息平台配置",
            manager=ap.platform_cfg,
            schema=schema.CONFIG_PLATFORM_SCHEMA,
            doc_link="https://docs.langbot.app/config/function/platform.html"
        )

        ap.settings_mgr.register_manager(
            name="provider.json",
            description="大模型能力配置",
            manager=ap.provider_cfg,
            schema=schema.CONFIG_PROVIDER_SCHEMA,
            doc_link="https://docs.langbot.app/config/function/provider.html"
        )

        ap.settings_mgr.register_manager(
            name="system.json",
            description="系统配置",
            manager=ap.system_cfg,
            schema=schema.CONFIG_SYSTEM_SCHEMA,
            doc_link="https://docs.langbot.app/config/function/system.html"
        )

        ap.plugin_setting_meta = await config.load_json_config("plugins/plugins.json", "templates/plugin-settings.json")
        await ap.plugin_setting_meta.dump_config()

        ap.sensitive_meta = await config.load_json_config("data/metadata/sensitive-words.json", "templates/metadata/sensitive-words.json")
        await ap.sensitive_meta.dump_config()

        ap.adapter_qq_botpy_meta = await config.load_json_config("data/metadata/adapter-qq-botpy.json", "templates/metadata/adapter-qq-botpy.json")
        await ap.adapter_qq_botpy_meta.dump_config()

        ap.llm_models_meta = await config.load_json_config("data/metadata/llm-models.json", "templates/metadata/llm-models.json")
        await ap.llm_models_meta.dump_config()

        ap.instance_secret_meta = await config.load_json_config("data/metadata/instance-secret.json", template_data={
            'jwt_secret': secrets.token_hex(16)
        })
        await ap.instance_secret_meta.dump_config()
