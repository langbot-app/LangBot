"""Small HTTP client for the versioned Pipeline Application API.

This module intentionally talks to the Service API over HTTP. It does not
import the server's Application object, persistence layer, or authorization
context, so it can be used by a local CLI or another process safely.
"""

from __future__ import annotations

import typing

import httpx

from .api import PipelineExtensionsUpdateInput


class ApplicationAPIClientError(RuntimeError):
    """Raised when the LangBot Service API rejects an operation."""

    def __init__(self, message: str, *, status_code: int | None = None, code: typing.Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class ApplicationAPIClient:
    """HTTP client for the four Pipeline Application API operations."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip('/'),
            headers={'X-API-Key': api_key},
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ApplicationAPIClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def list_pipelines(
        self,
        *,
        sort_by: str = 'created_at',
        sort_order: str = 'DESC',
    ) -> list[dict]:
        payload = self._request(
            'GET',
            '/api/v1/pipelines',
            params={'sort_by': sort_by, 'sort_order': sort_order},
        )
        return payload.get('pipelines', [])

    def get_pipeline(self, pipeline_uuid: str) -> dict | None:
        payload = self._request('GET', f'/api/v1/pipelines/{pipeline_uuid}')
        return payload.get('pipeline')

    def get_pipeline_extensions(self, pipeline_uuid: str) -> dict:
        return self._request('GET', f'/api/v1/pipelines/{pipeline_uuid}/extensions')

    def update_pipeline_extensions(
        self,
        pipeline_uuid: str,
        *,
        bound_plugins: list[dict],
        bound_mcp_servers: list[str],
        bound_skills: list[str],
        bound_mcp_resources: list[dict],
        enable_all_plugins: bool,
        enable_all_mcp_servers: bool,
        enable_all_skills: bool,
        mcp_resource_agent_read_enabled: bool,
    ) -> None:
        input = PipelineExtensionsUpdateInput(
            pipeline_uuid=pipeline_uuid,
            bound_plugins=bound_plugins,
            bound_mcp_servers=bound_mcp_servers,
            bound_skills=bound_skills,
            bound_mcp_resources=bound_mcp_resources,
            enable_all_plugins=enable_all_plugins,
            enable_all_mcp_servers=enable_all_mcp_servers,
            enable_all_skills=enable_all_skills,
            mcp_resource_agent_read_enabled=mcp_resource_agent_read_enabled,
        )
        self._request(
            'PUT',
            f'/api/v1/pipelines/{pipeline_uuid}/extensions',
            json={
                'bound_plugins': input.bound_plugins,
                'bound_mcp_servers': input.bound_mcp_servers,
                'bound_skills': input.bound_skills,
                'bound_mcp_resources': input.bound_mcp_resources,
                'enable_all_plugins': input.enable_all_plugins,
                'enable_all_mcp_servers': input.enable_all_mcp_servers,
                'enable_all_skills': input.enable_all_skills,
                'mcp_resource_agent_read_enabled': input.mcp_resource_agent_read_enabled,
            },
        )

    def _request(self, method: str, path: str, **kwargs: typing.Any) -> dict:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApplicationAPIClientError(str(exc)) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise ApplicationAPIClientError(
                'LangBot returned a non-JSON response',
                status_code=response.status_code,
                code='invalid_response',
            ) from exc
        if not isinstance(payload, dict):
            raise ApplicationAPIClientError(
                'LangBot returned an invalid JSON response',
                status_code=response.status_code,
                code='invalid_response',
            )
        if response.status_code >= 400 or payload.get('code') not in (0, None):
            raise ApplicationAPIClientError(
                str(payload.get('msg') or payload.get('message') or 'LangBot request failed'),
                status_code=response.status_code,
                code=payload.get('error_code') or payload.get('code') or 'request_failed',
            )
        data = payload.get('data', {})
        if not isinstance(data, dict):
            raise ApplicationAPIClientError(
                'LangBot returned an invalid data payload',
                status_code=response.status_code,
                code='invalid_response',
            )
        return data


__all__ = ['ApplicationAPIClient', 'ApplicationAPIClientError']
