import ast
from pathlib import Path
import re
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCALES = ('en', 'zh', 'ja')


class PlatformMessageDocsTests(unittest.TestCase):
    def test_locales_describe_standard_reply_contract(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                content = (ROOT / locale / 'plugin/dev/apis/platform.mdx').read_text(encoding='utf-8')
                for term in ('MessageResult', 'message_id', 'Quote.id', 'origin', 'thread_ts', 'str(message_chain)'):
                    self.assertIn(term, content)

    def test_reply_examples_match_and_parse_in_all_locales(self):
        examples = []
        for locale in LOCALES:
            content = (ROOT / locale / 'plugin/dev/apis/platform.mdx').read_text(encoding='utf-8')
            blocks = re.findall(r'```python\n(.*?)\n```', content, re.DOTALL)
            replies = [block for block in blocks if 'Quote(id=message_id' in block]
            self.assertEqual(len(replies), 1, locale)
            example = replies[0]
            ast.parse('async def example():\n' + textwrap.indent(example, '    '))
            self.assertIn('result.get("message_id")', example)
            self.assertIn('origin=MessageChain([])', example)
            examples.append(example)
        self.assertEqual(examples, [examples[0]] * len(LOCALES))
