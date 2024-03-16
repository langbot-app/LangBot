from __future__ import annotations

from .. import stage, app
from ..bootutils import config


@stage.stage_class("LoadConfigStage")
class LoadConfigStage(stage.BootingStage):
    """加载配置文件阶段
    """

    async def run(self, ap: app.Application):
        """启动
        """
        ap.command_cfg = await config.load_json_config("data/config/command.json", "templates/command.json")
        ap.pipeline_cfg = await config.load_json_config("data/config/pipeline.json", "templates/pipeline.json")
        ap.platform_cfg = await config.load_json_config("data/config/platform.json", "templates/platform.json")
        ap.provider_cfg = await config.load_json_config("data/config/provider.json", "templates/provider.json")
        ap.system_cfg = await config.load_json_config("data/config/system.json", "templates/system.json")

        ap.plugin_setting_meta = await config.load_json_config("plugins/plugins.json", "templates/plugin-settings.json")
        await ap.plugin_setting_meta.dump_config()

        ap.sensitive_meta = await config.load_json_config("data/metadata/sensitive-words.json", "templates/metadata/sensitive-words.json")
        await ap.sensitive_meta.dump_config()

        ap.adapter_qq_botpy_meta = await config.load_json_config("data/metadata/adapter-qq-botpy.json", "templates/metadata/adapter-qq-botpy.json")
        await ap.adapter_qq_botpy_meta.dump_config()

        ap.llm_models_meta = await config.load_json_config("data/metadata/llm-models.json", "templates/metadata/llm-models.json")
        await ap.llm_models_meta.dump_config()
