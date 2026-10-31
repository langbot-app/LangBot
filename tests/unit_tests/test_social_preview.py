import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('social_preview', ROOT / 'src/langbot/pkg/api/http/controller/social_preview.py')
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SocialPreviewTest(unittest.TestCase):
    def test_cloud_has_crawler_visible_image(self):
        html = (ROOT / 'web/index.html').read_text()
        result = module.cloud_preview_html(html, 'cloud.langbot.app')
        self.assertIn(module.CLOUD_IMAGE, result)
        self.assertIn('summary_large_image', result)
        self.assertEqual(result.count('property="og:image"'), 1)
        self.assertTrue((ROOT / 'web/public/social/cloud-v3.png').is_file())

    def test_self_hosted_is_unchanged(self):
        html = '<head><title>LangBot</title></head>'
        for host in ['localhost:5300', 'example.com', 'cloud.langbot.app.evil.com']:
            self.assertEqual(module.cloud_preview_html(html, host), html)


if __name__ == '__main__':
    unittest.main()
