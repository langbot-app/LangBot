from __future__ import annotations

import sys
import types
import unittest
import logging
from importlib.util import find_spec
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
logging.disable(logging.CRITICAL)


def _install_optional_dependency_stubs() -> None:
    # Presence is probed without importing: importing the real PyMuPDF here would
    # put its module-level page state into this process, which the isolation
    # tests assert never happens.
    if find_spec('markdown') is None:
        markdown_module = types.ModuleType('markdown')
        markdown_module.markdown = lambda text, extensions=None: text
        sys.modules['markdown'] = markdown_module

    if find_spec('fitz') is None and find_spec('pymupdf') is None:
        sys.modules['fitz'] = types.ModuleType('fitz')


_install_optional_dependency_stubs()


class GeneralParsersConfigTests(unittest.IsolatedAsyncioTestCase):
    def _parser_with_config(self, config: dict | None = None):
        from components.general_parsers.general_parsers import GeneralParsers

        class Plugin:
            called = False

            def get_config(self) -> dict:
                return config or {}

            async def invoke_llm(self, *args, **kwargs):
                self.called = True
                raise AssertionError('vision model should not be invoked')

        plugin = Plugin()
        parser = GeneralParsers()
        parser.plugin = plugin
        return parser, plugin

    async def test_enable_vision_false_suppresses_configured_model(self) -> None:
        from langbot_plugin.api.entities.builtin.rag.models import ParseContext

        parser, plugin = self._parser_with_config({
            'enable_vision': False,
            'vision_llm_model_uuid': 'vision-model',
        })

        result = await parser.parse(
            ParseContext(
                file_content=b'not a real image',
                filename='diagram.png',
                mime_type='image/png',
            )
        )

        self.assertFalse(plugin.called)
        self.assertEqual(result.text, '[图片文件: diagram.png]')
        self.assertFalse(result.metadata['vision_used'])

    async def test_mime_type_overrides_conflicting_filename_extension(self) -> None:
        from langbot_plugin.api.entities.builtin.rag.models import ParseContext

        parser, _ = self._parser_with_config()

        result = await parser.parse(
            ParseContext(
                file_content=b'<html><body><h1>HTML Title</h1><p>Body</p></body></html>',
                filename='wrong.txt',
                mime_type='text/html',
            )
        )

        self.assertEqual(result.metadata['extension'], 'html')
        self.assertEqual(result.metadata['extension_source'], 'mime_type')
        self.assertIn('extension_warning', result.metadata)
        self.assertIn('# HTML Title', result.text)

    async def test_parse_failure_is_reported_in_metadata(self) -> None:
        from langbot_plugin.api.entities.builtin.rag.models import ParseContext

        parser, _ = self._parser_with_config()

        result = await parser.parse(
            ParseContext(
                file_content=b'not a real pdf',
                filename='broken.pdf',
                mime_type='application/pdf',
            )
        )

        self.assertEqual(result.text, '')
        self.assertTrue(result.metadata['parser_failed'])
        self.assertIn('parse_error', result.metadata)

    async def test_section_content_includes_heading_for_langrag_indexing(self) -> None:
        from langbot_plugin.api.entities.builtin.rag.models import ParseContext

        parser, _ = self._parser_with_config()

        result = await parser.parse(
            ParseContext(
                file_content=b'<html><body><h2>Structured Output</h2><p>Body text</p></body></html>',
                filename='doc.html',
                mime_type='text/html',
            )
        )

        self.assertEqual(result.sections[0].heading, 'Structured Output')
        self.assertEqual(result.sections[0].level, 2)
        self.assertTrue(result.sections[0].content.startswith('Structured Output\n'))
        self.assertIn('Body text', result.sections[0].content)


class HtmlParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_nested_html_preserves_headings_and_markdown_tables(self) -> None:
        from components.general_parsers.parsers.html_text import parse_html

        html = b'''
        <html><body>
          <main><section>
            <h1>Title</h1>
            <p>Intro paragraph</p>
            <table><tr><th>A</th></tr><tr><td>B</td></tr></table>
          </section></main>
        </body></html>
        '''

        text, metadata = await parse_html(html, 'nested.html')

        self.assertIn('# Title', text)
        self.assertIn('Intro paragraph', text)
        self.assertIn('| A |', text)
        self.assertIn('| --- |', text)
        self.assertIn('| B |', text)
        self.assertLess(text.index('# Title'), text.index('Intro paragraph'))
        self.assertLess(text.index('Intro paragraph'), text.index('| A |'))
        self.assertFalse(metadata['has_images'])

    async def test_html_uses_detected_encoding(self) -> None:
        from components.general_parsers.parsers.html_text import parse_html

        html = '<html><body><p>中文内容</p></body></html>'.encode('gbk')

        text, _ = await parse_html(html, 'gbk.html')

        self.assertIn('中文内容', text)

    async def test_inline_image_vision_failure_keeps_text_and_placeholder(self) -> None:
        from components.general_parsers.parsers.html_text import parse_html

        async def failing_vision(image_b64: str, prompt: str) -> str:
            raise RuntimeError('vision service unavailable')

        html = b'''
        <html><body>
          <p>before <img src="data:image/png;base64,AAAA" alt="diagram"> after</p>
        </body></html>
        '''

        text, metadata = await parse_html(html, 'image.html', invoke_vision=failing_vision)

        self.assertIn('before', text)
        self.assertIn('[图片: HTML图片1]', text)
        self.assertIn('diagram', text)
        self.assertIn('after', text)
        self.assertFalse(metadata['vision_used'])
        self.assertEqual(metadata['vision_tasks_count'], 1)
        self.assertEqual(metadata['vision_images_described_count'], 0)
        self.assertEqual(metadata['vision_failed_count'], 1)


class ImageParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_image_vision_failure_returns_placeholder(self) -> None:
        from components.general_parsers.parsers.image import parse_image

        async def failing_vision(image_b64: str, prompt: str) -> str:
            raise RuntimeError('vision service unavailable')

        text, metadata = await parse_image(b'image bytes', 'photo.png', invoke_vision=failing_vision)

        self.assertEqual(text, '[图片文件: photo.png]')
        self.assertFalse(metadata['vision_used'])
        self.assertEqual(metadata['vision_tasks_count'], 1)
        self.assertEqual(metadata['vision_images_described_count'], 0)
        self.assertEqual(metadata['vision_failed_count'], 1)


class PdfVisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_pdf_vision_task_failures_are_counted_without_losing_successes(self) -> None:
        from components.general_parsers.parsers.pdf import _process_vision_tasks

        async def mixed_vision(image_b64: str, prompt: str) -> str:
            if image_b64 == 'fail':
                raise RuntimeError('vision service unavailable')
            return 'recognized diagram'

        text, stats = await _process_vision_tasks(
            '<!-- PAGE:1 -->\n[图片: 第1页-图片1]\n\n<!-- PAGE:2 -->\n',
            [
                {
                    'type': 'embedded_image',
                    'page': 1,
                    'img_idx': 0,
                    'image_b64': 'ok',
                    'placeholder': '[图片: 第1页-图片1]',
                },
                {
                    'type': 'scanned_page',
                    'page': 2,
                    'image_b64': 'fail',
                },
            ],
            mixed_vision,
        )

        self.assertIn('[图片描述: recognized diagram]', text)
        self.assertEqual(stats['vision_images_described_count'], 1)
        self.assertEqual(stats['vision_scanned_pages_count'], 0)
        self.assertEqual(stats['vision_failed_count'], 1)


class UtilsTests(unittest.TestCase):
    def test_count_words_counts_latin_words_and_cjk_characters(self) -> None:
        from components.general_parsers.utils import count_words

        self.assertEqual(count_words("hello world 中国"), 4)
        self.assertEqual(count_words("O'Reilly co-op"), 2)


if __name__ == '__main__':
    unittest.main()
