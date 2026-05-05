"""HTTP Request Node - make HTTP API calls

Node metadata is loaded from: ../../templates/metadata/nodes/http_request.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('http_request')
class HTTPRequestNode(WorkflowNode):
    """HTTP request node - make HTTP API calls"""

    type_name = "http_request"
    category = "process"
    icon = "🌐"
    name = "http_request"
    description = "http_request"
    name_zh = "HTTP 请求"
    name_en = "HTTP Request"
    description_zh = "向外部 API 发送 HTTP 请求"
    description_en = "Make HTTP requests to external APIs"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        import aiohttp

        url = self.get_config("url", "")
        method = self.get_config("method", "GET")
        timeout = self.get_config("timeout", 30)
        content_type = self.get_config("content_type", "application/json")

        headers = inputs.get("headers", {})
        headers["Content-Type"] = content_type

        auth_type = self.get_config("auth_type", "none")
        auth_config = self.get_config("auth_config", {})

        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
        elif auth_type == "api_key":
            header_name = auth_config.get("header", "X-API-Key")
            headers[header_name] = auth_config.get("key", "")

        body = inputs.get("body")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method, url=url,
                    json=body if content_type == "application/json" else None,
                    data=body if content_type != "application/json" else None,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    try:
                        response_data = await response.json()
                    except Exception:
                        response_data = await response.text()

                    return {"response": response_data, "status_code": response.status, "headers": dict(response.headers)}
        except Exception as e:
            return {"response": None, "status_code": 0, "headers": {}, "error": str(e)}
