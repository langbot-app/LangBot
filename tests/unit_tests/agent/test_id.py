"""Tests for agent runner ID parsing and formatting."""
from __future__ import annotations

import pytest

from langbot.pkg.agent.runner.id import (
    parse_runner_id,
    format_runner_id,
    RunnerIdParts,
    is_plugin_runner_id,
)


class TestRunnerIdParsing:
    """Tests for parse_runner_id."""

    def test_parse_plugin_runner_id(self):
        """Parse valid plugin runner ID."""
        runner_id = 'plugin:langbot-team/LocalAgent/default'
        parts = parse_runner_id(runner_id)

        assert parts.source == 'plugin'
        assert parts.plugin_author == 'langbot-team'
        assert parts.plugin_name == 'LocalAgent'
        assert parts.runner_name == 'default'

    def test_parse_plugin_runner_id_complex_names(self):
        """Parse plugin runner ID with complex names."""
        runner_id = 'plugin:alice/helpdesk-agent/ticket-handler'
        parts = parse_runner_id(runner_id)

        assert parts.source == 'plugin'
        assert parts.plugin_author == 'alice'
        assert parts.plugin_name == 'helpdesk-agent'
        assert parts.runner_name == 'ticket-handler'

    def test_parse_invalid_plugin_runner_id_missing_parts(self):
        """Parse invalid plugin runner ID with missing parts."""
        runner_id = 'plugin:langbot-team/LocalAgent'

        with pytest.raises(ValueError) as exc_info:
            parse_runner_id(runner_id)

        assert 'Invalid plugin runner ID format' in str(exc_info.value)

    def test_parse_invalid_plugin_runner_id_empty_parts(self):
        """Parse invalid plugin runner ID with empty parts."""
        runner_id = 'plugin://default'

        with pytest.raises(ValueError) as exc_info:
            parse_runner_id(runner_id)

        assert 'non-empty' in str(exc_info.value)

    def test_parse_invalid_runner_id_not_plugin(self):
        """Parse invalid runner ID without plugin prefix."""
        runner_id = 'local-agent'

        with pytest.raises(ValueError) as exc_info:
            parse_runner_id(runner_id)

        assert 'Invalid runner ID format' in str(exc_info.value)

    def test_parse_invalid_runner_id_empty_string(self):
        """Parse empty runner ID."""
        runner_id = ''

        with pytest.raises(ValueError):
            parse_runner_id(runner_id)


class TestRunnerIdFormatting:
    """Tests for format_runner_id."""

    def test_format_plugin_runner_id(self):
        """Format plugin runner ID."""
        runner_id = format_runner_id(
            source='plugin',
            plugin_author='langbot-team',
            plugin_name='LocalAgent',
            runner_name='default',
        )

        assert runner_id == 'plugin:langbot-team/LocalAgent/default'

    def test_format_invalid_source(self):
        """Format runner ID with invalid source."""
        with pytest.raises(ValueError) as exc_info:
            format_runner_id(
                source='builtin',
                plugin_author='langbot-team',
                plugin_name='LocalAgent',
                runner_name='default',
            )

        assert 'Invalid runner source' in str(exc_info.value)


class TestRunnerIdParts:
    """Tests for RunnerIdParts dataclass."""

    def test_get_plugin_id(self):
        """Get plugin ID from parts."""
        parts = RunnerIdParts(
            source='plugin',
            plugin_author='langbot-team',
            plugin_name='LocalAgent',
            runner_name='default',
        )

        assert parts.to_plugin_id() == 'langbot-team/LocalAgent'

    def test_frozen_dataclass(self):
        """RunnerIdParts should be immutable."""
        parts = RunnerIdParts(
            source='plugin',
            plugin_author='langbot-team',
            plugin_name='LocalAgent',
            runner_name='default',
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            parts.plugin_author = 'other'


class TestIsPluginRunnerId:
    """Tests for is_plugin_runner_id."""

    def test_is_plugin_runner_id_true(self):
        """Check plugin runner ID returns True."""
        assert is_plugin_runner_id('plugin:langbot-team/LocalAgent/default') is True

    def test_is_plugin_runner_id_false(self):
        """Check non-plugin runner ID returns False."""
        assert is_plugin_runner_id('local-agent') is False
        assert is_plugin_runner_id('builtin:local-agent') is False
        assert is_plugin_runner_id('') is False