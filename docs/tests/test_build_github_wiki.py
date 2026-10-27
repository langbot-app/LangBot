from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build-github-wiki.py"
SPEC = importlib.util.spec_from_file_location("build_github_wiki", MODULE_PATH)
assert SPEC and SPEC.loader
wiki = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki)


class BuildGitHubWikiTest(unittest.TestCase):
    def test_converts_frontmatter_callout_links_and_images(self) -> None:
        source = PurePosixPath("zh/insight/guide.mdx")
        title, output = wiki.convert_mdx(
            source,
            '''---
title: "开始使用"
description: "ignored"
---
<Tip title="提示">
阅读[模型文档](/zh/usage/models/readme)。
</Tip>

![界面](/images/ui.png)
''',
        )
        self.assertEqual(title, "开始使用")
        self.assertTrue(output.startswith("# 开始使用\n"))
        self.assertNotIn("description:", output)
        self.assertIn("> [!TIP]", output)
        self.assertIn("> **提示**", output)
        self.assertIn("[模型文档](zh-usage-models-readme)", output)
        self.assertIn(
            "https://raw.githubusercontent.com/langbot-app/langbot-docs/main/images/ui.png",
            output,
        )

    def test_resolves_relative_document_links(self) -> None:
        source = PurePosixPath("en/usage/mcp/readme.mdx")
        self.assertEqual(
            wiki.resolve_doc_target(source, "../models/readme#tools"),
            "en-usage-models-readme#tools",
        )
        self.assertEqual(
            wiki.resolve_doc_target(source, "../../deploy/settings.html"),
            "en-deploy-settings",
        )
        self.assertEqual(
            wiki.resolve_doc_target(source, "/en/deploy/pipelines/readme#request-variables"),
            "en-usage-pipelines-readme#request-variables",
        )

    def test_build_creates_flat_pages_and_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for language in wiki.LANGUAGES:
                path = root / language / "guide.mdx"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"---\ntitle: {language} Guide\n---\nContent\n", encoding="utf-8")
            output = root / "out"
            count = wiki.build(root, output)
            self.assertEqual(count, 3)
            self.assertTrue((output / "zh-guide.md").is_file())
            self.assertIn("[zh Guide](zh-guide)", (output / "_Sidebar.md").read_text())
            self.assertTrue((output / "Home.md").is_file())

    def test_sidebar_follows_docs_navigation_hierarchy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            documents = {
                "zh/insight/guide.mdx": "---\ntitle: 中文首页\n---\nContent\n",
                "zh/usage/models/readme.mdx": "---\ntitle: 模型配置\n---\nContent\n",
                "zh/usage/models/custom.mdx": "---\ntitle: 自定义模型\n---\nContent\n",
                "en/insight/guide.mdx": "---\ntitle: English Home\n---\nContent\n",
                "ja/insight/guide.mdx": "---\ntitle: 日本語ホーム\n---\nContent\n",
            }
            for relative, content in documents.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            (root / "docs.json").write_text(
                json.dumps(
                    {
                        "navigation": {
                            "languages": [
                                {
                                    "language": "cn",
                                    "tabs": [
                                        {
                                            "tab": "指南",
                                            "groups": [
                                                {"group": "快速开始", "pages": ["zh/insight/guide"]},
                                                {
                                                    "group": "配置 AI",
                                                    "pages": [
                                                        "zh/usage/models/readme",
                                                        {
                                                            "group": "模型供应商",
                                                            "pages": ["zh/usage/models/custom"],
                                                        },
                                                    ],
                                                },
                                            ],
                                        }
                                    ],
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            output = root / "out"
            wiki.build(root, output)
            sidebar = (output / "_Sidebar.md").read_text(encoding="utf-8")

            self.assertIn("<summary><strong>简体中文</strong></summary>", sidebar)
            self.assertIn("<summary>指南</summary>", sidebar)
            self.assertIn("- **快速开始**", sidebar)
            self.assertIn("  - [中文首页](zh-insight-guide)", sidebar)
            self.assertIn("  - **模型供应商**", sidebar)
            self.assertIn("    - [自定义模型](zh-usage-models-custom)", sidebar)
            self.assertLess(sidebar.index("中文首页"), sidebar.index("模型配置"))


if __name__ == "__main__":
    unittest.main()
