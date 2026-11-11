"""Compatibility re-export.

The component/page manifest helpers live in
:mod:`langbot_plugin.cli.utils.page_components` (their historical location).
This module only re-exports them so callers that imported the ``utils`` path
during a short-lived refactor keep working. New code should import from the
canonical ``cli.utils`` path.
"""

from __future__ import annotations

from langbot_plugin.cli.utils.page_components import (
    discover_plugin_components,
    populate_plugin_pages,
)

__all__ = ["discover_plugin_components", "populate_plugin_pages"]
