"""
sys.modules isolation utilities for breaking circular import chains.

Provides safe, reversible sys.modules manipulation for tests that need to
import modules with heavy import-time side effects (auto-registration,
circular dependencies, etc.).

Usage pattern:
    1. Create mock objects for modules that cause circular imports
    2. Use isolated_sys_modules to temporarily patch sys.modules
    3. Import target module after patching
    4. Test the real production code
    5. Context manager automatically restores original sys.modules state

Key principle: mock only what breaks the import chain, not what the code needs.
"""

from __future__ import annotations

import sys
import enum
from contextlib import contextmanager
from typing import Generator
from unittest.mock import MagicMock


class MockLifecycleControlScope(enum.Enum):
    """Mock enum for breaking circular import in core.entities."""
    APPLICATION = 'application'
    PLATFORM = 'platform'
    PLUGIN = 'plugin'
    PROVIDER = 'provider'


@contextmanager
def isolated_sys_modules(
    mocks: dict[str, object],
    clear: list[str] | None = None,
) -> Generator[None, None, None]:
    """
    Context manager for isolated sys.modules manipulation.

    Safely patches sys.modules with mocks and clears specified modules,
    then restores original state on exit. This prevents test pollution
    where mocks leak into subsequent tests.

    Args:
        mocks: Dict mapping module names to mock objects.
               These will be set in sys.modules during the context.
        clear: List of module names to remove from sys.modules before
               entering the context. Useful for forcing re-import of
               modules that depend on mocked modules.

    Example:
        >>> with isolated_sys_modules(
        ...     mocks={'my_pkg.heavy_module': MagicMock()},
        ...     clear=['my_pkg.target_module'],
        ... ):
        ...     from my_pkg.target_module import MyClass  # Safe import

    Note:
        - Modules in both mocks and clear will be mocked (not cleared)
        - Original state is restored even if exception occurs
        - Modules not in sys.modules before context are removed after
        - Package attributes (e.g., my_pkg.submodule) are also saved/restored
    """
    clear = clear or []
    touched = set(mocks.keys()) | set(clear)

    # Save original state for modules we'll touch
    saved: dict[str, object] = {}
    for name in touched:
        if name in sys.modules:
            saved[name] = sys.modules[name]

    # Save original package attributes that will be updated
    saved_attrs: dict[str, tuple[str, object]] = {}
    for mock_name, (pkg_name, attr_name) in _PACKAGE_ATTRIBUTE_UPDATES.items():
        if mock_name in mocks and pkg_name in sys.modules:
            pkg = sys.modules[pkg_name]
            if hasattr(pkg, attr_name):
                saved_attrs[mock_name] = (pkg_name, getattr(pkg, attr_name))

    try:
        # Clear modules first (force re-import)
        for name in clear:
            if name not in mocks:  # Don't clear if we're mocking it
                sys.modules.pop(name, None)

        # Apply mocks
        for name, module in mocks.items():
            sys.modules[name] = module

        # Update package attributes to point to mocks
        # This is critical because `from package import submodule` gets the attribute,
        # not sys.modules directly
        for mock_name, (pkg_name, attr_name) in _PACKAGE_ATTRIBUTE_UPDATES.items():
            if mock_name in mocks and pkg_name in sys.modules:
                setattr(sys.modules[pkg_name], attr_name, mocks[mock_name])

        yield

    finally:
        # Restore original state - critical for test isolation
        for name in touched:
            if name in saved:
                sys.modules[name] = saved[name]
            else:
                # Wasn't in sys.modules originally, remove it
                sys.modules.pop(name, None)

        # Restore package attributes
        for mock_name, (pkg_name, original_value) in saved_attrs.items():
            if pkg_name in sys.modules:
                setattr(sys.modules[pkg_name], _PACKAGE_ATTRIBUTE_UPDATES[mock_name][1], original_value)


def make_pipeline_handler_import_mocks() -> dict[str, MagicMock]:
    """
    Create mock objects needed to break circular import chain in handlers.

    The import chain:
        handler → core.app → pipeline.controller → http_controller
        → groups/plugins → taskmgr (partial init)

    This function creates minimal mocks that break this chain without
    affecting the handler's ability to use real pipeline.entities
    (needed for ResultType enum comparisons).

    Returns:
        Dict mapping module names to MagicMock objects.

    Note:
        These mocks are intentionally minimal - they only provide what's
        needed to prevent circular imports. The actual handler code uses
        real imports from langbot_plugin.api and langbot.pkg.pipeline.entities.
    """
    # Mock core.entities with proper Enum class
    mock_entities = MagicMock()
    mock_entities.LifecycleControlScope = MockLifecycleControlScope

    # Mock core.app - Application class is referenced but not instantiated
    mock_app = MagicMock()

    # Mock provider.runner - has preregistered_runners attribute
    mock_runner = MagicMock()
    mock_runner.preregistered_runners = []  # Empty by default, tests override

    # Mock utils.importutil - prevents auto-import of runners
    mock_importutil = MagicMock()
    mock_importutil.import_modules_in_pkg = lambda pkg: None
    mock_importutil.import_modules_in_pkgs = lambda pkgs: None

    return {
        'langbot.pkg.core.entities': mock_entities,
        'langbot.pkg.core.app': mock_app,
        'langbot.pkg.pipeline.controller': MagicMock(),
        'langbot.pkg.pipeline.pipelinemgr': MagicMock(),
        'langbot.pkg.pipeline.process.process': MagicMock(),
        'langbot.pkg.provider.runner': mock_runner,
        'langbot.pkg.utils.importutil': mock_importutil,
    }


# Package attributes that need to be updated alongside sys.modules mocking.
# When Python imports a submodule (e.g., langbot.pkg.provider.runner), it
# automatically sets an attribute on the parent package. The import statement
# `from ....provider import runner` gets this attribute, not sys.modules directly.
# This dict maps mock module names to the parent packages that need attribute updates.
_PACKAGE_ATTRIBUTE_UPDATES: dict[str, tuple[str, str]] = {
    'langbot.pkg.provider.runner': ('langbot.pkg.provider', 'runner'),
}


def get_handler_modules_to_clear(handler_name: str) -> list[str]:
    """
    Get list of handler-related modules to clear before import.

    These modules need to be cleared so they're re-imported after
    the circular import chain is mocked. Without clearing, they'd
    already be in sys.modules (possibly partially initialized).

    Args:
        handler_name: The handler file name (e.g., 'chat', 'command')

    Returns:
        List of module names to clear.
    """
    return [
        'langbot.pkg.pipeline.process.handler',
        'langbot.pkg.pipeline.process.handlers',
        f'langbot.pkg.pipeline.process.handlers.{handler_name}',
    ]