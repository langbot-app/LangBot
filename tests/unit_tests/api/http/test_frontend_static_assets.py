from __future__ import annotations

import gzip
from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.controller import main as controller_main
from langbot.pkg.utils import paths


@pytest.fixture
async def static_client(tmp_path, monkeypatch):
    assets = tmp_path / 'assets'
    assets.mkdir()
    javascript = b'window.previewLoaded = true;\n' * 100
    (assets / 'index-AbCd1234.js').write_bytes(javascript)
    (assets / 'index-AbCd1234.js.gz').write_bytes(gzip.compress(javascript))
    (assets / 'legacy-XyZa1234.js').write_bytes(javascript)
    (tmp_path / 'index.html').write_text('<html>current entry</html>')
    (tmp_path / 'settings.json').write_text('{}')
    monkeypatch.setattr(paths, 'get_frontend_path', lambda: str(tmp_path))
    monkeypatch.setattr(controller_main.group, 'preregistered_groups', [])
    controller = controller_main.HTTPController(SimpleNamespace())
    await controller.register_routes()
    return controller.quart_app.test_client(), javascript


async def test_gzip_static_asset_keeps_javascript_type_and_decodes_exactly(static_client):
    client, original = static_client
    response = await client.get('/assets/index-AbCd1234.js', headers={'Accept-Encoding': 'gzip, deflate'})
    assert response.status_code == 200
    assert response.headers['Content-Encoding'] == 'gzip'
    assert response.mimetype == 'application/javascript'
    body = await response.get_data()
    assert gzip.decompress(body) == original
    assert int(response.headers['Content-Length']) == len(body) < len(original)
    assert 'Accept-Encoding' in response.vary
    assert response.headers['Cache-Control'] == 'public, max-age=31536000, immutable'


@pytest.mark.parametrize('encoding', ['', 'identity', 'gzip;q=0, identity;q=1'])
async def test_client_can_decline_gzip(static_client, encoding):
    client, original = static_client
    response = await client.get('/assets/index-AbCd1234.js', headers={'Accept-Encoding': encoding})
    assert response.status_code == 200
    assert 'Content-Encoding' not in response.headers
    assert await response.get_data() == original
    assert 'Accept-Encoding' in response.vary


async def test_old_build_without_precompressed_asset_still_loads(static_client):
    client, original = static_client
    response = await client.get('/assets/legacy-XyZa1234.js', headers={'Accept-Encoding': 'gzip'})
    assert response.status_code == 200
    assert 'Content-Encoding' not in response.headers
    assert await response.get_data() == original


async def test_html_and_unversioned_config_remain_uncached(static_client):
    client, _ = static_client
    for path in ('/', '/home?action=showWorkspaceSettings', '/settings.json'):
        response = await client.get(path, headers={'Accept-Encoding': 'gzip'})
        assert response.status_code == 200
        assert 'no-store' in response.headers['Cache-Control']
        assert 'Content-Encoding' not in response.headers


async def test_compressed_asset_supports_conditional_requests(static_client):
    client, _ = static_client
    first = await client.get('/assets/index-AbCd1234.js', headers={'Accept-Encoding': 'gzip'})
    cached = await client.get(
        '/assets/index-AbCd1234.js',
        headers={
            'Accept-Encoding': 'gzip',
            'If-None-Match': first.headers['ETag'],
        },
    )
    assert cached.status_code == 304
    assert await cached.get_data() == b''
