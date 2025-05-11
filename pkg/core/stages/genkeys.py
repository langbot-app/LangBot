from __future__ import annotations

import secrets

from .. import stage, app


@stage.stage_class('GenKeysStage')
class GenKeysStage(stage.BootingStage):
    """生成密钥阶段"""

    async def run(self, ap: app.Application):
        """启动"""

        if not ap.instance_config.data['system']['jwt']['secret']:
            ap.instance_config.data['system']['jwt']['secret'] = secrets.token_hex(16)
            await ap.instance_config.dump_config()
