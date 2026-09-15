import base64
import datetime
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import pytest
from quart import Quart

from langbot.pkg.storage.media import MediaCache, SAFE_MEDIA_FILENAME
from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.api.http.controller.groups.files import FilesRouterGroup


class TestMediaCache:
    def setup_method(self):
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_storage_mgr = Mock()
        self.mock_provider = Mock()
        self.mock_provider.__class__.__name__ = 'LocalStorageProvider'
        self.mock_provider.exists = AsyncMock(return_value=False)
        self.mock_provider.save = AsyncMock()
        self.mock_provider.load = AsyncMock()
        self.mock_storage_mgr.storage_provider = self.mock_provider
        self.mock_storage_mgr._load_object_bounded = AsyncMock()
        self.media_cache = MediaCache(self.mock_app, self.mock_storage_mgr)

    def test_safe_media_filename_regex(self):
        assert SAFE_MEDIA_FILENAME.match('3f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3c.png')
        assert SAFE_MEDIA_FILENAME.match('3f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3c.jpg')
        assert SAFE_MEDIA_FILENAME.match('3f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3c')
        assert not SAFE_MEDIA_FILENAME.match('../etc/passwd')
        assert not SAFE_MEDIA_FILENAME.match('foo/bar.png')
        assert not SAFE_MEDIA_FILENAME.match('test.exe')
        assert not SAFE_MEDIA_FILENAME.match('3f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3cXpng')

    def test_hash_bytes(self):
        data1 = b'hello image content'
        data2 = b'hello image content'
        data3 = b'different content'
        assert self.media_cache.hash_bytes(data1) == self.media_cache.hash_bytes(data2)
        assert self.media_cache.hash_bytes(data1) != self.media_cache.hash_bytes(data3)

    def test_parse_data_url(self):
        raw = b'png binary data here'
        b64_str = base64.b64encode(raw).decode('ascii')
        data_url = f'data:image/png;base64,{b64_str}'

        parsed = self.media_cache.parse_data_url(data_url)
        assert parsed is not None
        data, mime = parsed
        assert data == raw
        assert mime == 'image/png'

    @pytest.mark.asyncio
    async def test_save_media_deduplication(self):
        raw = b'fake png bytes'
        hash_str = self.media_cache.hash_bytes(raw)

        # First save: provider.exists is False -> calls provider.save
        h1, key1, size1 = await self.media_cache.save_media(raw, 'image/png')
        assert h1 == hash_str
        assert key1 == f'media_cache/{hash_str}.png'
        assert size1 == len(raw)
        self.mock_provider.save.assert_called_once_with(key1, raw)

        # Second save: provider.exists is True -> does not call provider.save again
        self.mock_provider.exists.return_value = True
        self.mock_provider.save.reset_mock()
        h2, key2, size2 = await self.media_cache.save_media(raw, 'image/png')
        assert h2 == h1
        assert key2 == key1
        self.mock_provider.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_media(self):
        raw = b'stored bytes'
        self.mock_provider.exists.return_value = True
        self.mock_storage_mgr._load_object_bounded.return_value = raw

        valid_name = '3f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3c.png'
        res = await self.media_cache.get_media(valid_name)
        assert res is not None
        data, mime = res
        assert data == raw
        assert mime == 'image/png'

        # Rejects invalid names
        assert await self.media_cache.get_media('../malicious.png') is None

    @pytest.mark.asyncio
    async def test_externalize_chain_dump(self):
        raw = b'tiny image'
        b64 = f'data:image/png;base64,{base64.b64encode(raw).decode("ascii")}'
        chain_dump = [
            {'type': 'Plain', 'text': 'hello'},
            {'type': 'Image', 'url': 'https://multimedia.nt.qq.com.cn/download?appid=1407', 'base64': b64},
            {'type': 'Quote', 'origin': [{'type': 'Image', 'url': '', 'base64': b64}]},
        ]

        result = await self.media_cache.externalize_chain_dump(chain_dump)

        # Root image
        img = result[1]
        assert img['base64'] is None
        assert img['hash'] == self.media_cache.hash_bytes(raw)
        assert img['storage_key'].startswith('media_cache/')
        assert img['original_url'] == 'https://multimedia.nt.qq.com.cn/download?appid=1407'
        assert img['url'] == f'/api/v1/files/media/{img["hash"]}.png'
        assert img['size'] == len(raw)

        # Nested quote image
        nested_img = result[2]['origin'][0]
        assert nested_img['base64'] is None
        assert nested_img['hash'] == self.media_cache.hash_bytes(raw)
        assert nested_img['url'] == f'/api/v1/files/media/{nested_img["hash"]}.png'

    @pytest.mark.asyncio
    async def test_externalize_chain_dump_error_resilience(self):
        raw = b'broken image'
        b64 = f'data:image/png;base64,{base64.b64encode(raw).decode("ascii")}'
        chain_dump = [{'type': 'Image', 'base64': b64}]

        with patch.object(self.media_cache, 'save_media', side_effect=OSError('Disk full')):
            result = await self.media_cache.externalize_chain_dump(chain_dump)
            # Should not raise; base64 should be stripped as fallback
            assert result[0]['base64'] is None

    @pytest.mark.asyncio
    async def test_cleanup_retention_and_max_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            cache_dir = base_path / 'data' / 'storage' / 'media_cache'
            cache_dir.mkdir(parents=True)

            # Create 3 test files with different mtimes and sizes
            f1 = cache_dir / 'old_expired.png'
            f1.write_bytes(b'x' * 1000)
            old_time = (datetime.datetime.now() - datetime.timedelta(days=35)).timestamp()
            os.utime(f1, (old_time, old_time))

            f2 = cache_dir / 'recent_large1.png'
            f2.write_bytes(b'x' * 500)
            t2 = (datetime.datetime.now() - datetime.timedelta(days=5)).timestamp()
            os.utime(f2, (t2, t2))

            f3 = cache_dir / 'recent_large2.png'
            f3.write_bytes(b'x' * 500)
            t3 = (datetime.datetime.now() - datetime.timedelta(days=1)).timestamp()
            os.utime(f3, (t3, t3))

            with patch('langbot.pkg.storage.media.Path') as mock_path:
                mock_path.return_value = base_path / 'data' / 'storage'
                # Run cleanup with 30-day retention and max_size_mb = 0 (unlimited)
                stats = await self.media_cache.cleanup(retention_days=30, max_size_mb=0)
                assert stats['expired_deleted'] == 1
                assert not f1.exists()
                assert f2.exists()
                assert f3.exists()

                # Run cleanup with max_size_mb limited to ~0.0006 MB (< 1000 bytes)
                # Total is currently 1000 bytes (f2=500 + f3=500). Max size 600 bytes -> oldest f2 must be purged
                stats2 = await self.media_cache.cleanup(retention_days=30, max_size_mb=0.0006)
                assert stats2['size_deleted'] >= 1
                assert not f2.exists()
                assert f3.exists()

    @pytest.mark.asyncio
    async def test_files_media_endpoint(self):
        quart_app = Quart(__name__)
        mock_app = Mock()
        mock_app.storage_mgr = self.mock_storage_mgr

        router = FilesRouterGroup(mock_app, quart_app)
        await router.initialize()

        client = quart_app.test_client()

        # 1. 404 on not found
        mock_cache = Mock()
        mock_cache.get_media = AsyncMock(return_value=None)
        self.mock_storage_mgr.media_cache = mock_cache
        resp_404 = await client.get('/api/v1/files/media/3f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3c.png')
        assert resp_404.status_code == 404

        # 2. 200 on found with cache headers
        mock_cache.get_media.return_value = (b'fake image data', 'image/png')
        resp_200 = await client.get('/api/v1/files/media/3f8a9b1c2d3e4f5a6b7c8d9e0f1a2b3c.png')
        assert resp_200.status_code == 200
        assert await resp_200.get_data() == b'fake image data'
        assert 'public' in resp_200.headers.get('Cache-Control', '')
        assert 'image/png' in resp_200.headers.get('Content-Type', '')


class TestMonitoringServiceSanitization:
    def test_sanitize_oversized_base64_payload(self):
        svc = MonitoringService.__new__(MonitoringService)
        small_content = '{"type": "Image", "base64": "data:image/png;base64,tiny"}'
        # Should leave small contents untouched
        assert svc._sanitize_message_content(small_content) == small_content

        # Large content with base64 data URL
        huge_b64 = 'A' * 60000
        large_content = f'{{"type": "Image", "base64": "data:image/png;base64,{huge_b64}"}}'
        sanitized = svc._sanitize_message_content(large_content)
        assert huge_b64 not in sanitized
        assert '"base64": null' in sanitized or '"base64":null' in sanitized

        # Non-JSON content with multi-line base64
        multiline_b64 = ('A' * 70 + '\r\n') * 300
        raw_corrupted = 'prefix data:image/png;base64,' + multiline_b64 + ' suffix'
        sanitized_raw = svc._sanitize_message_content(raw_corrupted)
        assert '[base64 image omitted]' in sanitized_raw
        assert multiline_b64 not in sanitized_raw
