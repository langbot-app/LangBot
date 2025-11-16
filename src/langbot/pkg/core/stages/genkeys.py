from __future__ import annotations

import secrets

from .. import stage, app


@stage.stage_class('GenKeysStage')
class GenKeysStage(stage.BootingStage):
    """Generate keys stage"""

    async def run(self, ap: app.Application):
        """Generate keys"""

        if not ap.instance_config.data['system']['jwt']['secret']:
            ap.instance_config.data['system']['jwt']['secret'] = secrets.token_hex(16)
            await ap.instance_config.dump_config()

        if 'recovery_key' not in ap.instance_config.data['system']:
            ap.instance_config.data['system']['recovery_key'] = ''

        if not ap.instance_config.data['system']['recovery_key']:
            ap.instance_config.data['system']['recovery_key'] = secrets.token_hex(3).upper()
            await ap.instance_config.dump_config()
