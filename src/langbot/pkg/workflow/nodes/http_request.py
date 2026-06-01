"""HTTP Request Node - make HTTP API calls

Node metadata is loaded from: ../../templates/metadata/nodes/http_request.yaml
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Any
from urllib.parse import urlparse

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)

# 内网地址黑名单
_PRIVATE_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]

# 危险协议
_DANGEROUS_SCHEMES = {'file', 'gopher', 'dict', 'ftp', 'telnet'}


def _is_safe_url(url: str) -> tuple[bool, str]:
    """检查 URL 是否安全（非内网地址）"""
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f'Invalid URL: {e}'

    # 检查协议
    scheme = parsed.scheme.lower()
    if scheme in _DANGEROUS_SCHEMES:
        return False, f'Dangerous scheme: {scheme}'

    if scheme not in ('http', 'https'):
        return False, f'Unsupported scheme: {scheme}'

    # 检查主机名
    hostname = parsed.hostname
    if not hostname:
        return False, 'Missing hostname'

    # 检查是否是危险主机名
    dangerous_hosts = {'localhost', '0.0.0.0', '127.0.0.1', '::1'}
    if hostname.lower() in dangerous_hosts:
        return False, f'Dangerous hostname: {hostname}'

    # 解析 IP 地址并检查是否在私有网络
    try:
        ip = ipaddress.ip_address(hostname)
        for network in _PRIVATE_NETWORKS:
            if ip in network:
                return False, f'Private network address: {ip}'
    except ValueError:
        # 不是 IP 地址，尝试 DNS 解析检查
        # 这里可以添加 DNS 解析检查，但为了避免复杂性，暂时跳过
        pass

    return True, ''


@workflow_node('http_request')
class HTTPRequestNode(WorkflowNode):
    """HTTP request node - make HTTP API calls"""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        import aiohttp

        url = self.get_config('url', '')
        method = self.get_config('method', 'GET').upper()
        timeout = self.get_config('timeout', 30)
        content_type = self.get_config('content_type', 'application/json')
        allow_redirects = self.get_config('allow_redirects', False)  # 默认禁用重定向

        # 限制超时时间
        timeout = min(max(timeout, 1), 120)

        if not url:
            return {'response': None, 'status_code': 0, 'headers': {}, 'error': 'No URL provided'}

        # 安全检查 URL
        is_safe, error_msg = _is_safe_url(url)
        if not is_safe:
            logger.warning('Unsafe URL blocked: %s - %s', url, error_msg)
            return {'response': None, 'status_code': 0, 'headers': {}, 'error': f'Unsafe URL: {error_msg}'}

        # 验证 HTTP 方法
        allowed_methods = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
        if method not in allowed_methods:
            return {'response': None, 'status_code': 0, 'headers': {}, 'error': f'Invalid method: {method}'}

        # 创建 headers 副本，避免修改输入
        headers = dict(inputs.get('headers', {}))
        headers['Content-Type'] = content_type

        auth_type = self.get_config('auth_type', 'none')
        auth_config = self.get_config('auth_config', {})

        if auth_type == 'bearer':
            headers['Authorization'] = f'Bearer {auth_config.get("token", "")}'
        elif auth_type == 'api_key':
            header_name = auth_config.get('header', 'X-API-Key')
            headers[header_name] = auth_config.get('key', '')

        body = inputs.get('body')

        logger.info('HTTP %s %s (timeout=%s)', method, url, timeout)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    json=body if content_type == 'application/json' else None,
                    data=body if content_type != 'application/json' else None,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    allow_redirects=allow_redirects,
                ) as response:
                    try:
                        response_data = await response.json()
                    except Exception:
                        response_data = await response.text()

                    logger.info('HTTP %s %s -> %d', method, url, response.status)

                    return {
                        'response': response_data,
                        'status_code': response.status,
                        'headers': dict(response.headers),
                        'error': None,
                    }
        except aiohttp.ClientError as e:
            logger.error('HTTP request failed: %s', e)
            return {'response': None, 'status_code': 0, 'headers': {}, 'error': f'HTTP error: {e}'}
        except Exception as e:
            logger.error('HTTP request unexpected error: %s', e)
            return {'response': None, 'status_code': 0, 'headers': {}, 'error': f'Unexpected error: {e}'}
