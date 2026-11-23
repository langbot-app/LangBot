from __future__ import annotations

import logging
import secrets

from .. import stage, app

# This stage runs before SetupLoggerStage, so ap.logger is still None here;
# the module logger falls back to the stderr lastResort handler.
_logger = logging.getLogger(__name__)

# 32 symbols without 0/O or 1/I; eight independent draws provide 40 random bits.
_RECOVERY_KEY_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
_RECOVERY_KEY_LENGTH = 8


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
            # Keep recovery practical to type. Security also requires the reset
            # endpoint's concurrency-safe quota (five admissions per 15 minutes).
            ap.instance_config.data['system']['recovery_key'] = ''.join(
                secrets.choice(_RECOVERY_KEY_ALPHABET) for _ in range(_RECOVERY_KEY_LENGTH)
            )
            await ap.instance_config.dump_config()
        elif len(ap.instance_config.data['system']['recovery_key']) < _RECOVERY_KEY_LENGTH:
            _logger.warning(
                'Low-entropy legacy recovery key detected (length < 8); '
                'regenerate system.recovery_key in the configuration file '
                'with a strong random value (#2392)'
            )
