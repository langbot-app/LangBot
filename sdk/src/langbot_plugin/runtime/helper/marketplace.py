from __future__ import annotations

import json
import time

import httpx
from langbot_plugin.runtime.settings import settings as runtime_settings
import typing
from langbot_plugin.entities import marketplace as entities_marketplace

_MAX_MARKETPLACE_JSON_BYTES = 1024 * 1024
_MAX_PLUGIN_PACKAGE_BYTES = 64 * 1024 * 1024
_PROGRESS_INTERVAL_BYTES = 1024 * 1024


async def _read_limited(
    response: httpx.Response,
    *,
    max_bytes: int,
) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise RuntimeError("Marketplace response exceeds the runtime limit")
        except (TypeError, ValueError):
            pass
    body = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
        body.extend(chunk)
        if len(body) > max_bytes:
            raise RuntimeError("Marketplace response exceeds the runtime limit")
    return bytes(body)


async def _request_json(client: httpx.AsyncClient, url: str) -> dict:
    async with client.stream("GET", url) as response:
        if response.status_code != 200:
            raise RuntimeError(
                f"Marketplace request failed: HTTP {response.status_code}"
            )
        body = await _read_limited(
            response,
            max_bytes=_MAX_MARKETPLACE_JSON_BYTES,
        )
        payload = json.loads(body)
    if not isinstance(payload, dict):
        raise RuntimeError("Marketplace returned a non-object response")
    if payload.get("code") != 0:
        raise RuntimeError(f"Marketplace request failed: {payload.get('msg', '')}")
    return payload


async def get_plugin_info(
    plugin_author: str, plugin_name: str
) -> entities_marketplace.PluginInfo:
    cloud_service_url = runtime_settings.cloud_service_url
    url = (
        f"{cloud_service_url}/api/v1/marketplace/plugins/{plugin_author}/{plugin_name}"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        payload = await _request_json(client, url)
        return entities_marketplace.PluginInfo.model_validate(payload["data"]["plugin"])


async def download_plugin(
    plugin_author: str, plugin_name: str, plugin_version: str
) -> bytes:
    cloud_service_url = runtime_settings.cloud_service_url
    url = f"{cloud_service_url}/api/v1/marketplace/plugins/download/{plugin_author}/{plugin_name}/{plugin_version}"
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to download plugin: HTTP {response.status_code}"
                )
            return await _read_limited(
                response,
                max_bytes=_MAX_PLUGIN_PACKAGE_BYTES,
            )


async def download_plugin_streaming(
    plugin_author: str, plugin_name: str, plugin_version: str
) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
    """Download plugin with streaming progress.

    Yields dicts with keys: downloaded, total, speed, done, data (only when done=True).
    """
    cloud_service_url = runtime_settings.cloud_service_url
    url = f"{cloud_service_url}/api/v1/marketplace/plugins/download/{plugin_author}/{plugin_name}/{plugin_version}"

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to download plugin: HTTP {response.status_code}"
                )

            total = int(response.headers.get("content-length", 0))
            if total > _MAX_PLUGIN_PACKAGE_BYTES:
                raise RuntimeError("Plugin package exceeds the runtime limit")
            downloaded = 0
            package = bytearray()
            last_progress = 0
            start_time = time.time()

            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                package.extend(chunk)
                downloaded += len(chunk)
                if downloaded > _MAX_PLUGIN_PACKAGE_BYTES:
                    raise RuntimeError("Plugin package exceeds the runtime limit")
                elapsed = time.time() - start_time
                speed = downloaded / elapsed if elapsed > 0 else 0

                if downloaded - last_progress >= _PROGRESS_INTERVAL_BYTES:
                    last_progress = downloaded
                    yield {
                        "downloaded": downloaded,
                        "total": total,
                        "speed": speed,
                        "done": False,
                    }

            if downloaded > last_progress:
                yield {
                    "downloaded": downloaded,
                    "total": total,
                    "speed": downloaded / max(time.time() - start_time, 1e-9),
                    "done": False,
                }

        yield {
            "downloaded": downloaded,
            "total": total if total > 0 else downloaded,
            "speed": 0,
            "done": True,
            "data": bytes(package),
        }


async def list_plugins() -> list[entities_marketplace.PluginInfo]:
    cloud_service_url = runtime_settings.cloud_service_url
    url = f"{cloud_service_url}/api/v1/marketplace/plugins"
    async with httpx.AsyncClient(timeout=30) as client:
        payload = await _request_json(client, url)
        return [
            entities_marketplace.PluginInfo.model_validate(plugin)
            for plugin in payload["data"]["plugins"]
        ]
