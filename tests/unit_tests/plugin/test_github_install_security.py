from __future__ import annotations

import httpx
import pytest

from langbot.pkg.plugin import connector as connector_module

from .test_connector_methods import create_mock_connector


TRUSTED_LEGACY_REQUEST = {
    'owner': 'langbot-app',
    'repo': 'demo-plugin',
    'release_tag': 'v1.0.0',
    'asset_url': 'https://github.com/langbot-app/demo-plugin/releases/download/v1.0.0/demo.lbpkg',
}


def _patch_client(monkeypatch, handler):
    real_async_client = httpx.AsyncClient
    observed: list[dict] = []

    def client_factory(*args, **kwargs):
        observed.append(dict(kwargs))
        return real_async_client(
            transport=httpx.MockTransport(handler),
            follow_redirects=kwargs.get('follow_redirects', False),
            trust_env=kwargs.get('trust_env', True),
            timeout=kwargs.get('timeout'),
        )

    monkeypatch.setattr(connector_module.httpx, 'AsyncClient', client_factory)
    return observed


@pytest.mark.parametrize(
    'asset_url',
    [
        'http://127.0.0.1/internal.lbpkg',
        'https://169.254.169.254/latest/meta-data',
        'https://github.com@127.0.0.1/internal.lbpkg',
        'https://evil.example/langbot-app/demo-plugin/releases/download/v1.0.0/demo.lbpkg',
    ],
)
@pytest.mark.asyncio
async def test_github_install_rejects_internal_or_untrusted_asset_url_before_network(
    monkeypatch,
    asset_url,
):
    connector = create_mock_connector()
    monkeypatch.setattr(
        connector_module.httpx,
        'AsyncClient',
        lambda *_args, **_kwargs: pytest.fail('network client must not be created'),
    )

    with pytest.raises(ValueError, match='GitHub release asset URL'):
        await connector._download_github_package(
            {**TRUSTED_LEGACY_REQUEST, 'asset_url': asset_url},
            None,
        )


@pytest.mark.asyncio
async def test_github_asset_id_is_resolved_server_side_and_redirect_escape_is_rejected(
    monkeypatch,
):
    connector = create_mock_connector()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/releases/42'):
            return httpx.Response(
                200,
                json={
                    'id': 42,
                    'tag_name': 'v1.0.0',
                    'assets': [{'id': 99, 'size': 128, 'state': 'uploaded'}],
                },
            )
        if request.url.path.endswith('/releases/assets/99'):
            return httpx.Response(
                302,
                headers={'location': 'http://169.254.169.254/latest/meta-data'},
            )
        raise AssertionError(f'unexpected request: {request.url}')

    observed = _patch_client(monkeypatch, handler)
    with pytest.raises(ValueError, match='untrusted host'):
        await connector._download_github_package(
            {
                'owner': 'langbot-app',
                'repo': 'demo-plugin',
                'release_tag': 'v1.0.0',
                'release_id': 42,
                'asset_id': 99,
                'asset_url': 'https://attacker.invalid/ignored',
            },
            None,
        )

    assert len(observed) == 1
    assert observed[0]['trust_env'] is False
    assert observed[0]['follow_redirects'] is False


@pytest.mark.asyncio
async def test_github_download_rejects_oversized_content_length(monkeypatch):
    connector = create_mock_connector()
    monkeypatch.setattr(connector_module, '_GITHUB_PLUGIN_DOWNLOAD_MAX_BYTES', 8)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={'content-length': '9'}, content=b'')

    _patch_client(monkeypatch, handler)
    with pytest.raises(ValueError, match='10 MiB download limit'):
        await connector._download_github_package(TRUSTED_LEGACY_REQUEST, None)


@pytest.mark.asyncio
async def test_github_download_counts_chunked_stream_bytes(monkeypatch):
    connector = create_mock_connector()
    monkeypatch.setattr(connector_module, '_GITHUB_PLUGIN_DOWNLOAD_MAX_BYTES', 8)

    class ChunkedBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'1234'
            yield b'56789'

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=ChunkedBody())

    _patch_client(monkeypatch, handler)
    with pytest.raises(ValueError, match='10 MiB download limit'):
        await connector._download_github_package(TRUSTED_LEGACY_REQUEST, None)


@pytest.mark.asyncio
async def test_github_asset_id_download_allows_github_object_redirect(monkeypatch):
    connector = create_mock_connector()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/releases/42'):
            return httpx.Response(
                200,
                json={
                    'id': 42,
                    'tag_name': 'v1.0.0',
                    'assets': [{'id': 99, 'size': 7, 'state': 'uploaded'}],
                },
            )
        if request.url.path.endswith('/releases/assets/99'):
            return httpx.Response(
                302,
                headers={
                    'location': 'https://release-assets.githubusercontent.com/github-production-release-asset/demo'
                },
            )
        if request.url.host == 'release-assets.githubusercontent.com':
            return httpx.Response(200, content=b'package')
        raise AssertionError(f'unexpected request: {request.url}')

    _patch_client(monkeypatch, handler)
    package = await connector._download_github_package(
        {
            'owner': 'langbot-app',
            'repo': 'demo-plugin',
            'release_tag': 'v1.0.0',
            'release_id': 42,
            'asset_id': 99,
        },
        None,
    )

    assert package == b'package'
