"""HTTP Request Node - make HTTP API calls

Node metadata is loaded from: ../../templates/metadata/nodes/http_request.yaml
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from ...utils.outbound_url import assert_safe_outbound_url

from langbot.pkg.workflow.protocol.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)


def _is_safe_url(url: str) -> tuple[bool, str]:
    try:
        assert_safe_outbound_url(url)
    except ValueError as exc:
        return False, str(exc)
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

        # 限制超时时间
        timeout = min(max(timeout, 1), 120)

        if not url:
            return {'response': None, 'status_code': 0, 'headers': {}, 'error': 'No URL provided'}

        # 安全检查 URL
        is_safe, error_msg = await asyncio.to_thread(_is_safe_url, url)
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
                    allow_redirects=False,
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
