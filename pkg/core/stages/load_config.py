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
