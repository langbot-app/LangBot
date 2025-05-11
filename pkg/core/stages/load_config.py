from __future__ import annotations

import os

from .. import stage, app
from ..bootutils import config


@stage.stage_class('LoadConfigStage')
class LoadConfigStage(stage.BootingStage):
    """加载配置文件阶段"""

    async def run(self, ap: app.Application):
        """启动"""

        # ======= deprecated =======
        if os.path.exists('data/config/command.json'):
            ap.command_cfg = await config.load_json_config(
                'data/config/command.json',
                'templates/legacy/command.json',
                completion=False,
            )

        if os.path.exists('data/config/pipeline.json'):
            ap.pipeline_cfg = await config.load_json_config(
                'data/config/pipeline.json',
                'templates/legacy/pipeline.json',
                completion=False,
            )

        if os.path.exists('data/config/platform.json'):
            ap.platform_cfg = await config.load_json_config(
                'data/config/platform.json',
                'templates/legacy/platform.json',
                completion=False,
            )

        if os.path.exists('data/config/provider.json'):
            ap.provider_cfg = await config.load_json_config(
                'data/config/provider.json',
                'templates/legacy/provider.json',
                completion=False,
            )

        if os.path.exists('data/config/system.json'):
            ap.system_cfg = await config.load_json_config(
                'data/config/system.json',
                'templates/legacy/system.json',
                completion=False,
            )

        # ======= deprecated =======

        ap.instance_config = await config.load_yaml_config(
            'data/config.yaml', 'templates/config.yaml', completion=False
        )
        await ap.instance_config.dump_config()

        ap.sensitive_meta = await config.load_json_config(
            'data/metadata/sensitive-words.json',
            'templates/metadata/sensitive-words.json',
        )
        await ap.sensitive_meta.dump_config()

        ap.pipeline_config_meta_trigger = await config.load_yaml_config(
            'templates/metadata/pipeline/trigger.yaml',
            'templates/metadata/pipeline/trigger.yaml',
        )
        ap.pipeline_config_meta_safety = await config.load_yaml_config(
            'templates/metadata/pipeline/safety.yaml',
            'templates/metadata/pipeline/safety.yaml',
        )
        ap.pipeline_config_meta_ai = await config.load_yaml_config(
            'templates/metadata/pipeline/ai.yaml', 'templates/metadata/pipeline/ai.yaml'
        )
        ap.pipeline_config_meta_output = await config.load_yaml_config(
            'templates/metadata/pipeline/output.yaml',
            'templates/metadata/pipeline/output.yaml',
        )
