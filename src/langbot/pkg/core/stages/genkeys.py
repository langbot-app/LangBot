from __future__ import annotations

import logging
import secrets

from .. import stage, app

# This stage runs before SetupLoggerStage, so ap.logger is still None here;
# the module logger falls back to the stderr lastResort handler.
_logger = logging.getLogger(__name__)


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
            # 256-bit key, aligned with the API key strength; the legacy 24-bit
            # key (token_hex(3)) was brute-forceable within hours (#2392).
            ap.instance_config.data['system']['recovery_key'] = secrets.token_urlsafe(32)
            await ap.instance_config.dump_config()
        elif len(ap.instance_config.data['system']['recovery_key']) < 16:
            _logger.warning(
                'Low-entropy legacy recovery key detected (length < 16); '
                'regenerate system.recovery_key in the configuration file '
                'with a strong random value (#2392)'
            )
