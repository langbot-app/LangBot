"""Exercise pinned public asset caching without external network access."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from tools.regression import vdb_public_assets as assets


class Response(BytesIO):
    def geturl(self):
        return 'https://example.invalid/pinned'


class PublicAssetsTest(TestCase):
    def test_fetch_verifies_and_reuses_asset(self):
        with TemporaryDirectory() as folder:
            cache = Path(folder)
            digest = sha256(b'fixture').hexdigest()
            with mock.patch.object(assets, 'urlopen', return_value=Response(b'fixture')) as request:
                a = assets.fetch_asset(cache, 'asset', 'https://example.invalid/pinned', digest, 7)
                b = assets.fetch_asset(cache, 'asset', 'https://example.invalid/pinned', digest, 7)
                request.assert_called_once()
            self.assertEqual(a, b)
            self.assertEqual(a.read_bytes(), b'fixture')

    def test_bad_fetch_and_bad_cache_fail_closed(self):
        with TemporaryDirectory() as folder:
            cache = Path(folder)
            digest = sha256(b'fixture').hexdigest()
            for body, limit, error in ((b'bad', 7, 'SHA-256 mismatch'), (b'exceeds 7', 7, 'exceeds')):
                with mock.patch.object(assets, 'urlopen', return_value=Response(body)):
                    with self.assertRaisesRegex(ValueError, error):
                        assets.fetch_asset(cache, 'asset', 'https://example.invalid/pinned', digest, limit)
                self.assertEqual(list(cache.iterdir()), [])
            (cache / 'asset').write_bytes(b'bad cached copy')
            with mock.patch.object(assets, 'urlopen') as request:
                with self.assertRaisesRegex(ValueError, 'wrong SHA-256'):
                    assets.fetch_asset(cache, 'asset', 'https://example.invalid/pinned', digest, 7)
                request.assert_not_called()

    def test_rejects_non_https_before_request(self):
        with TemporaryDirectory() as folder, mock.patch.object(assets, 'urlopen') as request:
            with self.assertRaisesRegex(ValueError, 'non-HTTPS'):
                assets.fetch_asset(Path(folder), 'asset', 'http://example.invalid', 'a' * 64, 10)
            request.assert_not_called()

    def test_experiment_rejects_cache_or_output_inside_checkout(self):
        from tools.entrypoints.vdb_benchmark_local import ROOT, external_path

        with self.assertRaisesRegex(ValueError, 'outside the repository'):
            external_path(ROOT / 'results', '--output')
        with TemporaryDirectory() as folder:
            self.assertEqual(external_path(Path(folder), '--asset-cache'), Path(folder))
