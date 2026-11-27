from __future__ import annotations

import json

import pytest

from langbot_plugin.runtime.helper import marketplace


def _plugin_payload():
    return {
        "created_at": "2025-08-10T21:29:28.54938+08:00",
        "updated_at": "2025-08-11T14:17:19.223492+08:00",
        "deleted_at": None,
        "plugin_id": "tester/demo",
        "author": "tester",
        "name": "demo",
        "label": {"en_US": "Demo"},
        "description": {"en_US": "Demo plugin"},
        "icon": "icon.svg",
        "repository": "https://example.com/repo",
        "tags": None,
        "install_count": 1,
        "latest_version": "0.1.0",
        "status": "live",
    }


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json_data = json_data or {}
        if json_data is not None and not content:
            content = json.dumps(json_data).encode()
        self.content = content
        self.text = "response text"
        self.headers = {"content-length": str(len(content))}

    def json(self):
        return self._json_data

    async def aiter_bytes(self, chunk_size=8192):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]


class FakeStream:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeAsyncClient:
    response = FakeResponse()
    requests = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        self.requests.append(("GET", url))
        return self.response

    def stream(self, method, url):
        self.requests.append((method, url))
        return FakeStream(self.response)


@pytest.fixture(autouse=True)
def fake_client(monkeypatch):
    FakeAsyncClient.requests = []
    monkeypatch.setattr(marketplace.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        marketplace.runtime_settings, "cloud_service_url", "https://cloud"
    )
    return FakeAsyncClient


@pytest.mark.asyncio
async def test_get_plugin_info_validates_marketplace_response(fake_client):
    fake_client.response = FakeResponse(
        json_data={"code": 0, "data": {"plugin": _plugin_payload()}}
    )

    info = await marketplace.get_plugin_info("tester", "demo")

    assert info.plugin_id == "tester/demo"
    assert fake_client.requests == [
        ("GET", "https://cloud/api/v1/marketplace/plugins/tester/demo")
    ]


@pytest.mark.asyncio
async def test_download_plugin_returns_response_content(fake_client):
    fake_client.response = FakeResponse(content=b"package")

    assert await marketplace.download_plugin("tester", "demo", "0.1.0") == b"package"


@pytest.mark.asyncio
async def test_download_plugin_streaming_yields_progress_and_final_data(fake_client):
    fake_client.response = FakeResponse(content=b"abcdef")

    chunks = [
        chunk
        async for chunk in marketplace.download_plugin_streaming(
            "tester", "demo", "0.1.0"
        )
    ]

    assert chunks[0]["downloaded"] == 6
    assert chunks[0]["done"] is False
    assert chunks[-1]["done"] is True
    assert chunks[-1]["data"] == b"abcdef"


@pytest.mark.asyncio
async def test_list_plugins_validates_each_plugin(fake_client):
    fake_client.response = FakeResponse(
        json_data={"code": 0, "data": {"plugins": [_plugin_payload()]}}
    )

    plugins = await marketplace.list_plugins()

    assert [plugin.plugin_id for plugin in plugins] == ["tester/demo"]


@pytest.mark.asyncio
async def test_plugin_download_rejects_oversized_package(fake_client, monkeypatch):
    monkeypatch.setattr(marketplace, "_MAX_PLUGIN_PACKAGE_BYTES", 4)
    fake_client.response = FakeResponse(content=b"12345")

    with pytest.raises(RuntimeError, match="exceeds the runtime limit"):
        await marketplace.download_plugin("tester", "demo", "0.1.0")
