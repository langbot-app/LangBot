import pytest

from langbot.pkg.utils.runner import RunnerCategory, get_runner_category


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
def test_get_runner_category_returns_unknown_for_invalid_urls(runner_url):
    assert get_runner_category('dify-service-api', runner_url) == RunnerCategory.UNKNOWN


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
def test_get_runner_category_detects_local_hosts_with_ipaddress(runner_url):
    assert get_runner_category('langflow-api', runner_url) == RunnerCategory.LOCAL


@pytest.mark.parametrize(
    'runner_url',
    [
        'http://10.evil.com',
        'http://192.168.example.com',
    ],
)
def test_get_runner_category_does_not_treat_private_ip_prefix_domains_as_local(runner_url):
    assert get_runner_category('langflow-api', runner_url) == RunnerCategory.CLOUD
