from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse


class RunnerCategory:
    LOCAL = 'local'
    CLOUD = 'cloud'
    UNKNOWN = 'unknown'


CLOUD_DOMAINS = [
    '.n8n.cloud',
    '.n8n.io',
    'api.dify.ai',
    'cloud.dify.ai',
    '.coze.com',
    '.coze.cn',
    'cloud.langflow.ai',
    '.langflow.org',
]

LOCAL_PATTERNS = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    '192.168.',
    '10.',
    '172.16.',
    '172.17.',
    '172.18.',
    '172.19.',
    '172.20.',
    '172.21.',
    '172.22.',
    '172.23.',
    '172.24.',
    '172.25.',
    '172.26.',
    '172.27.',
    '172.28.',
    '172.29.',
    '172.30.',
    '172.31.',
]

HOST_LABEL_PATTERN = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')


def _is_valid_hostname(host: str) -> bool:
    if host == 'localhost':
        return True

    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass

    if not host or len(host) > 253 or any(char.isspace() for char in host):
        return False

    host = host.rstrip('.')
    if not host:
        return False

    return all(HOST_LABEL_PATTERN.match(label) for label in host.split('.'))


def _is_local_host(host: str) -> bool:
    if host == 'localhost':
        return True

    try:
        ip_address = ipaddress.ip_address(host)
    except ValueError:
        return False

    return ip_address.is_private or ip_address.is_loopback or ip_address.is_unspecified


def get_runner_category(runner_name: str, runner_url: str) -> str:
    if not runner_url:
        return RunnerCategory.UNKNOWN

    try:
        parsed_url = urlparse(runner_url)
        host = parsed_url.hostname.lower() if parsed_url.hostname else ''
        _ = parsed_url.port
    except Exception:
        return RunnerCategory.UNKNOWN

    if not parsed_url.scheme or not host or not _is_valid_hostname(host):
        return RunnerCategory.UNKNOWN

    if _is_local_host(host):
        return RunnerCategory.LOCAL

    for domain in CLOUD_DOMAINS:
        if host.endswith(domain):
            return RunnerCategory.CLOUD

    return RunnerCategory.CLOUD


def get_runner_info(runner_name: str, runner_url: str) -> dict:
    return {
        'name': runner_name,
        'url': runner_url,
        'category': get_runner_category(runner_name, runner_url),
    }


def is_cloud_runner(runner_name: str, runner_url: str) -> bool:
    return get_runner_category(runner_name, runner_url) == RunnerCategory.CLOUD


def is_local_runner(runner_name: str, runner_url: str) -> bool:
    return get_runner_category(runner_name, runner_url) == RunnerCategory.LOCAL


def extract_runner_url(runner_name: str, runner, pipeline_config: dict | None) -> str | None:
    if not runner or not hasattr(runner, 'pipeline_config'):
        return None

    ai_config = pipeline_config.get('ai', {}) if pipeline_config else {}

    if runner_name == 'dify-service-api':
        return ai_config.get('dify-service-api', {}).get('base-url')
    elif runner_name == 'n8n-service-api':
        return ai_config.get('n8n-service-api', {}).get('webhook-url')
    elif runner_name == 'coze-api':
        return ai_config.get('coze-api', {}).get('api-base')
    elif runner_name == 'langflow-api':
        return ai_config.get('langflow-api', {}).get('base-url')

    return None


def get_runner_category_from_runner(runner_name: str, runner, pipeline_config: dict | None) -> str:
    runner_url = extract_runner_url(runner_name, runner, pipeline_config)
    return get_runner_category(runner_name, runner_url)
