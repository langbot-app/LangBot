"""Agent runner ID parsing and formatting."""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class RunnerIdParts:
    """Parsed runner ID components."""
    source: str  # 'plugin' (future: 'builtin')
    plugin_author: str
    plugin_name: str
    runner_name: str

    def to_plugin_id(self) -> str:
        """Return plugin identifier as author/name."""
        return f'{self.plugin_author}/{self.plugin_name}'


def parse_runner_id(runner_id: str) -> RunnerIdParts:
    """Parse runner ID string into components.

    Args:
        runner_id: Runner ID in format 'plugin:author/plugin_name/runner_name'

    Returns:
        RunnerIdParts with parsed components

    Raises:
        ValueError: If runner_id format is invalid
    """
    if runner_id.startswith('plugin:'):
        parts = runner_id[7:].split('/')
        if len(parts) != 3:
            raise ValueError(
                f'Invalid plugin runner ID format: {runner_id}. '
                f'Expected: plugin:author/plugin_name/runner_name'
            )
        plugin_author, plugin_name, runner_name = parts
        if not plugin_author or not plugin_name or not runner_name:
            raise ValueError(
                f'Invalid plugin runner ID: {runner_id}. '
                f'author, plugin_name, and runner_name must be non-empty'
            )
        return RunnerIdParts(
            source='plugin',
            plugin_author=plugin_author,
            plugin_name=plugin_name,
            runner_name=runner_name,
        )
    else:
        # For backward compatibility with old built-in runner names
        # This should eventually be removed after migration
        raise ValueError(
            f'Invalid runner ID format: {runner_id}. '
            f'Expected: plugin:author/plugin_name/runner_name'
        )


def format_runner_id(
    source: str,
    plugin_author: str,
    plugin_name: str,
    runner_name: str,
) -> str:
    """Format runner ID from components.

    Args:
        source: Runner source ('plugin')
        plugin_author: Plugin author
        plugin_name: Plugin name
        runner_name: Runner component name

    Returns:
        Runner ID string
    """
    if source == 'plugin':
        return f'plugin:{plugin_author}/{plugin_name}/{runner_name}'
    else:
        raise ValueError(f'Invalid runner source: {source}')


def is_plugin_runner_id(runner_id: str) -> bool:
    """Check if runner ID is a plugin runner.

    Args:
        runner_id: Runner ID string

    Returns:
        True if runner ID starts with 'plugin:'
    """
    return runner_id.startswith('plugin:')