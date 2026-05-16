"""
Tests for langbot.pkg.utils.runner module.

Tests runner category detection functions:
- get_runner_category: categorizes runner URLs as local, cloud, or unknown
- is_cloud_runner / is_local_runner: helper functions
- extract_runner_url: extracts URL from runner config
- get_runner_info: returns runner info dict
"""

import pytest
from unittest.mock import Mock, patch

from langbot.pkg.utils.runner import (
    RunnerCategory,
    CLOUD_DOMAINS,
    LOCAL_PATTERNS,
    get_runner_category,
    get_runner_info,
    is_cloud_runner,
    is_local_runner,
    extract_runner_url,
    get_runner_category_from_runner,
)


class TestGetRunnerCategory:
    """Test runner category detection from URL."""

    def test_empty_url_returns_unknown(self):
        """Empty or None URL should return UNKNOWN."""
        assert get_runner_category("test", "") == RunnerCategory.UNKNOWN
        assert get_runner_category("test", None) == RunnerCategory.UNKNOWN

    def test_localhost_returns_local(self):
        """localhost URL should be categorized as LOCAL."""
        assert get_runner_category("test", "http://localhost:3000") == RunnerCategory.LOCAL
        assert get_runner_category("test", "https://localhost") == RunnerCategory.LOCAL

    def test_127_0_0_1_returns_local(self):
        """127.0.0.1 URL should be categorized as LOCAL."""
        assert get_runner_category("test", "http://127.0.0.1:8080") == RunnerCategory.LOCAL
        assert get_runner_category("test", "https://127.0.0.1") == RunnerCategory.LOCAL

    def test_0_0_0_0_returns_local(self):
        """0.0.0.0 URL should be categorized as LOCAL."""
        assert get_runner_category("test", "http://0.0.0.0:8080") == RunnerCategory.LOCAL

    def test_private_ip_192_168_returns_local(self):
        """192.168.x.x private IP should be categorized as LOCAL."""
        assert get_runner_category("test", "http://192.168.1.1:3000") == RunnerCategory.LOCAL
        assert get_runner_category("test", "http://192.168.0.100") == RunnerCategory.LOCAL

    def test_private_ip_10_returns_local(self):
        """10.x.x.x private IP should be categorized as LOCAL."""
        assert get_runner_category("test", "http://10.0.0.1:8080") == RunnerCategory.LOCAL
        assert get_runner_category("test", "http://10.255.255.255") == RunnerCategory.LOCAL

    def test_private_ip_172_16_31_returns_local(self):
        """172.16.x.x - 172.31.x.x private IP range should be categorized as LOCAL."""
        assert get_runner_category("test", "http://172.16.0.1:8080") == RunnerCategory.LOCAL
        assert get_runner_category("test", "http://172.20.0.1") == RunnerCategory.LOCAL
        assert get_runner_category("test", "http://172.31.255.255") == RunnerCategory.LOCAL

    def test_n8n_cloud_returns_cloud(self):
        """n8n.cloud domain should be categorized as CLOUD."""
        assert get_runner_category("test", "https://myinstance.n8n.cloud") == RunnerCategory.CLOUD
        assert get_runner_category("test", "https://test.n8n.io") == RunnerCategory.CLOUD

    def test_dify_cloud_returns_cloud(self):
        """Dify cloud domains should be categorized as CLOUD."""
        assert get_runner_category("test", "https://api.dify.ai/v1") == RunnerCategory.CLOUD
        assert get_runner_category("test", "https://cloud.dify.ai") == RunnerCategory.CLOUD

    def test_coze_cloud_returns_cloud(self):
        """Coze domains should be categorized as CLOUD."""
        assert get_runner_category("test", "https://api.coze.com") == RunnerCategory.CLOUD
        assert get_runner_category("test", "https://api.coze.cn") == RunnerCategory.CLOUD

    def test_langflow_cloud_returns_cloud(self):
        """Langflow domains should be categorized as CLOUD."""
        assert get_runner_category("test", "https://cloud.langflow.ai") == RunnerCategory.CLOUD
        assert get_runner_category("test", "https://test.langflow.org") == RunnerCategory.CLOUD

    def test_other_url_returns_cloud(self):
        """Other URLs should default to CLOUD category."""
        assert get_runner_category("test", "https://example.com") == RunnerCategory.CLOUD
        assert get_runner_category("test", "https://myserver.example.org") == RunnerCategory.CLOUD

    @pytest.mark.parametrize(
        'runner_url',
        [
            'api.dify.ai/v1',
            'localhost:7860',
            'https:///v1',
            'https://',
            'https://exa mple.com',
            'http://[::1',
            'http://localhost:bad',
        ],
    )
    def test_invalid_urls_return_unknown(self, runner_url):
        """Invalid or incomplete URLs should return UNKNOWN."""
        assert get_runner_category("test", runner_url) == RunnerCategory.UNKNOWN

    def test_urlparse_exception_returns_unknown(self):
        """Exception during URL parsing should return UNKNOWN."""
        # Test by mocking urlparse to raise an exception
        from langbot.pkg.utils import runner

        def mock_urlparse(url):
            raise Exception("URL parsing failed")

        with patch("langbot.pkg.utils.runner.urlparse", side_effect=mock_urlparse):
            result = runner.get_runner_category("test", "http://example.com")
            assert result == RunnerCategory.UNKNOWN

    def test_url_without_scheme_returns_unknown(self):
        """URL without scheme should return UNKNOWN."""
        assert get_runner_category("test", "example.com") == RunnerCategory.UNKNOWN

    @pytest.mark.parametrize(
        'runner_url',
        [
            'http://localhost:7860',
            'http://127.0.0.1:7860',
            'http://10.0.0.1:7860',
            'http://172.16.0.1:7860',
            'http://172.31.255.255:7860',
            'http://192.168.1.20:7860',
            'http://[::1]:7860',
        ],
    )
    def test_detects_local_hosts_with_ipaddress(self, runner_url):
        """Local hostnames and private IPs should be categorized as LOCAL."""
        assert get_runner_category('langflow-api', runner_url) == RunnerCategory.LOCAL

    @pytest.mark.parametrize(
        'runner_url',
        [
            'http://10.evil.com',
            'http://192.168.example.com',
        ],
    )
    def test_private_ip_prefix_domains_are_not_local(self, runner_url):
        """Domain names that only look like private IP prefixes should not be LOCAL."""
        assert get_runner_category('langflow-api', runner_url) == RunnerCategory.CLOUD

class TestIsCloudRunner:
    """Test is_cloud_runner helper function."""

    def test_cloud_runner_returns_true(self):
        """Cloud URL should return True."""
        assert is_cloud_runner("test", "https://api.dify.ai") is True

    def test_local_runner_returns_false(self):
        """Local URL should return False."""
        assert is_cloud_runner("test", "http://localhost:3000") is False

    def test_unknown_returns_false(self):
        """Unknown category should return False."""
        assert is_cloud_runner("test", None) is False


class TestIsLocalRunner:
    """Test is_local_runner helper function."""

    def test_local_runner_returns_true(self):
        """Local URL should return True."""
        assert is_local_runner("test", "http://localhost:3000") is True

    def test_cloud_runner_returns_false(self):
        """Cloud URL should return False."""
        assert is_local_runner("test", "https://api.dify.ai") is False

    def test_unknown_returns_false(self):
        """Unknown category should return False."""
        assert is_local_runner("test", None) is False


class TestGetRunnerInfo:
    """Test get_runner_info function."""

    def test_returns_dict_with_expected_keys(self):
        """Should return dict with name, url, and category keys."""
        info = get_runner_info("my-runner", "http://localhost:3000")
        assert "name" in info
        assert "url" in info
        assert "category" in info

    def test_includes_correct_values(self):
        """Should include correct values in dict."""
        info = get_runner_info("my-runner", "http://localhost:3000")
        assert info["name"] == "my-runner"
        assert info["url"] == "http://localhost:3000"
        assert info["category"] == RunnerCategory.LOCAL


class TestExtractRunnerUrl:
    """Test extract_runner_url function."""

    def test_dify_service_api_extracts_url(self):
        """Should extract base-url from dify-service-api config."""
        runner = Mock()
        runner.pipeline_config = {}
        pipeline_config = {
            "ai": {
                "dify-service-api": {"base-url": "https://api.dify.ai"}
            }
        }
        url = extract_runner_url("dify-service-api", runner, pipeline_config)
        assert url == "https://api.dify.ai"

    def test_n8n_service_api_extracts_url(self):
        """Should extract webhook-url from n8n-service-api config."""
        runner = Mock()
        runner.pipeline_config = {}
        pipeline_config = {
            "ai": {
                "n8n-service-api": {"webhook-url": "https://my.n8n.cloud/webhook"}
            }
        }
        url = extract_runner_url("n8n-service-api", runner, pipeline_config)
        assert url == "https://my.n8n.cloud/webhook"

    def test_coze_api_extracts_url(self):
        """Should extract api-base from coze-api config."""
        runner = Mock()
        runner.pipeline_config = {}
        pipeline_config = {
            "ai": {
                "coze-api": {"api-base": "https://api.coze.com"}
            }
        }
        url = extract_runner_url("coze-api", runner, pipeline_config)
        assert url == "https://api.coze.com"

    def test_langflow_api_extracts_url(self):
        """Should extract base-url from langflow-api config."""
        runner = Mock()
        runner.pipeline_config = {}
        pipeline_config = {
            "ai": {
                "langflow-api": {"base-url": "https://cloud.langflow.ai"}
            }
        }
        url = extract_runner_url("langflow-api", runner, pipeline_config)
        assert url == "https://cloud.langflow.ai"

    def test_unknown_runner_returns_none(self):
        """Unknown runner name should return None."""
        runner = Mock()
        runner.pipeline_config = {}
        pipeline_config = {}
        url = extract_runner_url("unknown-runner", runner, pipeline_config)
        assert url is None

    def test_none_runner_returns_none(self):
        """None runner should return None."""
        url = extract_runner_url("test", None, {})
        assert url is None

    def test_runner_without_pipeline_config_returns_none(self):
        """Runner without pipeline_config attribute should return None."""
        runner = Mock(spec=[])  # Empty spec means no attributes
        url = extract_runner_url("test", runner, {})
        assert url is None

    def test_none_pipeline_config_returns_none(self):
        """None pipeline_config should return None."""
        runner = Mock()
        runner.pipeline_config = {}
        url = extract_runner_url("dify-service-api", runner, None)
        assert url is None

    def test_missing_ai_config_returns_none(self):
        """Missing ai config should return None."""
        runner = Mock()
        runner.pipeline_config = {}
        pipeline_config = {}
        url = extract_runner_url("dify-service-api", runner, pipeline_config)
        assert url is None


class TestGetRunnerCategoryFromRunner:
    """Test get_runner_category_from_runner function."""

    def test_extracts_and_categorizes(self):
        """Should extract URL and return correct category."""
        runner = Mock()
        runner.pipeline_config = {}
        pipeline_config = {
            "ai": {
                "dify-service-api": {"base-url": "https://api.dify.ai"}
            }
        }
        category = get_runner_category_from_runner("dify-service-api", runner, pipeline_config)
        assert category == RunnerCategory.CLOUD

    def test_returns_unknown_for_missing_url(self):
        """Should return UNKNOWN when URL cannot be extracted."""
        runner = Mock()
        runner.pipeline_config = {}
        category = get_runner_category_from_runner("unknown", runner, {})
        assert category == RunnerCategory.UNKNOWN


class TestConstants:
    """Test that constants are properly defined."""

    def test_runner_category_constants(self):
        """RunnerCategory should have LOCAL, CLOUD, UNKNOWN."""
        assert RunnerCategory.LOCAL == "local"
        assert RunnerCategory.CLOUD == "cloud"
        assert RunnerCategory.UNKNOWN == "unknown"

    def test_cloud_domains_not_empty(self):
        """CLOUD_DOMAINS should not be empty."""
        assert len(CLOUD_DOMAINS) > 0

    def test_local_patterns_not_empty(self):
        """LOCAL_PATTERNS should not be empty."""
        assert len(LOCAL_PATTERNS) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
