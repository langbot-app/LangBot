"""Tests for DifyServiceAPIRunner pure utility methods.

Tests the helper methods that don't require real Dify API calls.
"""

from __future__ import annotations

import pytest


class TestDifyExtractTextOutput:
    """Tests for _extract_dify_text_output method."""

    def _create_runner(self):
        """Create runner instance."""
        from unittest.mock import MagicMock

        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner

        mock_app = MagicMock()
        pipeline_config = {
            'ai': {
                'dify-service-api': {
                    'app-type': 'chat',
                    'api-key': 'test-key',
                    'base-url': 'https://api.dify.ai',
                }
            },
            'output': {'misc': {}}
        }

        runner = DifyServiceAPIRunner(mock_app, pipeline_config)
        runner.dify_client = MagicMock()

        return runner

    def test_extract_none_value(self):
        """None returns empty string."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output(None)

        assert result == ''

    def test_extract_string_value(self):
        """Plain string is returned."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output('plain text')

        assert result == 'plain text'

    def test_extract_dict_with_content(self):
        """Dict with 'content' key extracts content."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output({'content': 'extracted content'})

        assert result == 'extracted content'

    def test_extract_dict_without_content(self):
        """Dict without 'content' key is JSON dumped."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output({'key': 'value'})

        assert 'key' in result
        assert 'value' in result

    def test_extract_json_string_with_content(self):
        """JSON string with 'content' key extracts content."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output('{"content": "json content"}')

        assert result == 'json content'

    def test_extract_json_string_without_content(self):
        """JSON string without 'content' key returns original."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output('{"other": "value"}')

        assert '{"other": "value"}' in result

    def test_extract_whitespace_string(self):
        """Whitespace string returns empty."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output('   ')

        assert result == ''


class TestDifyRunnerConfigValidation:
    """Tests for runner config validation."""

    def test_invalid_app_type_raises(self):
        """Invalid app-type raises DifyAPIError."""
        from unittest.mock import MagicMock

        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner
        from langbot.libs.dify_service_api.v1.errors import DifyAPIError

        mock_app = MagicMock()
        pipeline_config = {
            'ai': {
                'dify-service-api': {
                    'app-type': 'invalid-type',
                    'api-key': 'test',
                    'base-url': 'https://api.dify.ai',
                }
            },
            'output': {'misc': {}}
        }

        with pytest.raises(DifyAPIError, match='不支持'):
            DifyServiceAPIRunner(mock_app, pipeline_config)

    def test_valid_app_types(self):
        """Valid app-types don't raise."""
        from unittest.mock import MagicMock

        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner

        mock_app = MagicMock()

        for app_type in ['chat', 'agent', 'workflow']:
            pipeline_config = {
                'ai': {
                    'dify-service-api': {
                        'app-type': app_type,
                        'api-key': 'test',
                        'base-url': 'https://api.dify.ai',
                    }
                },
                'output': {'misc': {}}
            }

            runner = DifyServiceAPIRunner(mock_app, pipeline_config)
            # Should not raise
            assert runner is not None


class TestDifyRunnerInit:
    """Tests for runner initialization."""

    def test_runner_stores_config(self):
        """Runner stores pipeline_config."""
        from unittest.mock import MagicMock

        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner

        mock_app = MagicMock()
        pipeline_config = {
            'ai': {
                'dify-service-api': {
                    'app-type': 'chat',
                    'api-key': 'test-key',
                    'base-url': 'https://api.dify.ai',
                }
            },
            'output': {'misc': {}}
        }

        runner = DifyServiceAPIRunner(mock_app, pipeline_config)

        assert runner.pipeline_config == pipeline_config
        assert runner.ap == mock_app