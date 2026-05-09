"""Tests for AnthropicMessages requester.

Tests config and pure utility methods.
"""

from __future__ import annotations

from unittest.mock import MagicMock


class TestAnthropicMessagesConfig:
    """Tests for default config."""

    def test_default_config_values(self):
        """Check default_config."""
        from langbot.pkg.provider.modelmgr.requesters.anthropicmsgs import AnthropicMessages

        assert AnthropicMessages.default_config['base_url'] == 'https://api.anthropic.com'
        assert AnthropicMessages.default_config['timeout'] == 120

    def test_config_override(self):
        """Config can override defaults."""
        from langbot.pkg.provider.modelmgr.requesters.anthropicmsgs import AnthropicMessages

        mock_app = MagicMock()
        req = AnthropicMessages(mock_app, {
            'base_url': 'https://custom.anthropic.com',
            'timeout': 60,
        })

        assert req.requester_cfg['base_url'] == 'https://custom.anthropic.com'
        assert req.requester_cfg['timeout'] == 60