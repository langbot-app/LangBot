from __future__ import annotations

import secrets
import os

from .. import stage, app
from ..bootutils import config
from ...config import settings as settings_mgr


@stage.stage_class("LoadConfigStage")
class LoadConfigStage(stage.BootingStage):
    """加载配置文件阶段
    """

    async def run(self, ap: app.Application):
        """启动
        """
        
        ap.settings_mgr = settings_mgr.SettingsManager(ap)
        await ap.settings_mgr.initialize()

        if os.path.exists("data/config/command.json"):
            ap.command_cfg = await config.load_json_config("data/config/command.json", "templates/command.json", completion=False)

        if os.path.exists("data/config/pipeline.json"):
            ap.pipeline_cfg = await config.load_json_config("data/config/pipeline.json", "templates/pipeline.json", completion=False)

        if os.path.exists("data/config/platform.json"):
            ap.platform_cfg = await config.load_json_config("data/config/platform.json", "templates/platform.json", completion=False)

        if os.path.exists("data/config/provider.json"):
            ap.provider_cfg = await config.load_json_config("data/config/provider.json", "templates/provider.json", completion=False)

        if os.path.exists("data/config/system.json"):
            ap.system_cfg = await config.load_json_config("data/config/system.json", "templates/system.json", completion=False)

        ap.sensitive_meta = await config.load_json_config("data/metadata/sensitive-words.json", "templates/metadata/sensitive-words.json")
        await ap.sensitive_meta.dump_config()

        ap.instance_secret_meta = await config.load_json_config("data/metadata/instance-secret.json", template_data={
            'jwt_secret': secrets.token_hex(16)
        })
        await ap.instance_secret_meta.dump_config()

        ap.pipeline_config_meta_trigger = await config.load_yaml_config("templates/metadata/pipeline/trigger.yaml", "templates/metadata/pipeline/trigger.yaml")
        ap.pipeline_config_meta_safety = await config.load_yaml_config("templates/metadata/pipeline/safety.yaml", "templates/metadata/pipeline/safety.yaml")
        ap.pipeline_config_meta_ai = await config.load_yaml_config("templates/metadata/pipeline/ai.yaml", "templates/metadata/pipeline/ai.yaml")
        ap.pipeline_config_meta_output = await config.load_yaml_config("templates/metadata/pipeline/output.yaml", "templates/metadata/pipeline/output.yaml")
