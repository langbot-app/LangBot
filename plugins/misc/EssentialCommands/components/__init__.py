"""EssentialCommands components.

The command modules import the plugin-root ``i18n`` module. At runtime the SDK
imports them as ``components.commands.*`` with the plugin directory on
``sys.path``; this package initializer makes that explicit and holds the single,
guarded path insertion for the whole plugin (a package initializer runs exactly
once per process, before any command module body). Command modules must not
mutate ``sys.path`` themselves.
"""
from __future__ import annotations

import os
import sys

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)
