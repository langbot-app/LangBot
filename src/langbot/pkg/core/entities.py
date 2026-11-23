from __future__ import annotations

import enum


class LifecycleControlScope(enum.Enum):
    APPLICATION = 'application'
    PLATFORM = 'platform'
    PLUGIN = 'plugin'
    PROVIDER = 'provider'
