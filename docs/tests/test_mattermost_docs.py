"""Read-only contracts for Mattermost documentation translations; no network access."""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCALES = {"en": "en", "cn": "zh", "jp": "ja"}
GUIDE = "usage/platforms/mattermost"
IMAGE = re.compile(r"!\[([^\]]*)\]\((/images/[^)]+)\)")


class MattermostDocsTests(unittest.TestCase):
    def test_each_site_locale_has_a_guide_and_support_table_entry(self):
        docs = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))
        for language in docs["navigation"]["languages"]:
            locale = LOCALES[language["language"]]
            with self.subTest(locale=locale):
                guide = ROOT / f"{locale}/{GUIDE}.mdx"
                self.assertTrue(guide.is_file(), f"Missing translated guide: {guide}")
                readme = (guide.parent / "readme.mdx").read_text(encoding="utf-8")
                rows = [line for line in readme.splitlines() if line.startswith("| Mattermost |")]
                self.assertEqual(len(rows), 1)
                self.assertIn("✅", rows[0])
                self.assertIn(f"](/{locale}/{GUIDE})", rows[0])
                self.assertTrue(rows[0].split("|")[3].strip(), "Edition support notes missing")

    def test_each_site_locale_lists_mattermost_in_bot_navigation(self):
        docs = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))

        def page_lists(value):
            if isinstance(value, dict):
                if "pages" in value:
                    yield value["pages"]
                for child in value.values():
                    yield from page_lists(child)
            elif isinstance(value, list):
                for child in value:
                    yield from page_lists(child)

        for language in docs["navigation"]["languages"]:
            locale = LOCALES[language["language"]]
            with self.subTest(locale=locale):
                groups = [pages for pages in page_lists(language)
                          if f"{locale}/usage/platforms/slack" in pages]
                self.assertEqual(len(groups), 1)
                self.assertEqual(groups[0].count(f"{locale}/{GUIDE}"), 1)

    def test_translations_preserve_source_steps_permissions_and_assets(self):
        source = (ROOT / f"zh/{GUIDE}.mdx").read_text(encoding="utf-8")
        source_images = [url for _, url in IMAGE.findall(source)]
        for locale, screenshot_note in (("en", "Chinese"), ("ja", "中国語")):
            with self.subTest(locale=locale):
                path = ROOT / f"{locale}/{GUIDE}.mdx"
                self.assertTrue(path.is_file(), f"Missing translated guide: {path}")
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith('---\ntitle: "Mattermost"\n'))
                self.assertRegex(text, r'(?m)^description: ".+"$')
                self.assertIn('icon: "/images/platforms/mattermost.svg"', text)
                self.assertTrue((ROOT / "images/platforms/mattermost.svg").is_file())
                for permission in ("`post:all`", "`post:channels`"):
                    self.assertIn(permission, text)
                self.assertEqual(len(re.findall(r"^## ", text, re.M)),
                                 len(re.findall(r"^## ", source, re.M)))
                self.assertEqual(len(re.findall(r"^- ", text, re.M)),
                                 len(re.findall(r"^- ", source, re.M)))
                self.assertIn(screenshot_note, text)
                images = IMAGE.findall(text)
                self.assertEqual([url for _, url in images], source_images)
                for alt, url in images:
                    self.assertTrue(alt.strip(), "Translated screenshot alt text missing")
                    self.assertTrue((ROOT / url.lstrip("/")).is_file(), url)


if __name__ == "__main__":
    unittest.main()
