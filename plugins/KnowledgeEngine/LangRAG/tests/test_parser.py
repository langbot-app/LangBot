import codecs
import unittest
from unittest.mock import patch

from components.knowledge_engine.parser import FileParser


class FileParserEncodingTests(unittest.IsolatedAsyncioTestCase):
    async def test_utf8_punctuation_is_preserved_without_encoding_guesses(self):
        # Public LoCoMo conv-26 includes curly punctuation in session 14.
        text = "He's so cute! What’s the funniest thing Oliver's done?"
        parser = FileParser()

        for filename in ('conversation.txt', 'conversation.unknown'):
            for prefix in (b'', codecs.BOM_UTF8):
                with self.subTest(filename=filename, bom=bool(prefix)):
                    with patch(
                        'components.knowledge_engine.parser.chardet.detect',
                        return_value={'encoding': 'Windows-1252', 'confidence': 0.73},
                    ) as detect:
                        parsed = await parser.parse(prefix + text.encode('utf-8'), filename)

                    self.assertEqual(parsed, text)
                    detect.assert_not_called()

    async def test_unicode_boms_are_decoded_before_utf8(self):
        text = 'Meeting at 10 today.'
        parser = FileParser()

        for prefix, encoding in (
            (codecs.BOM_UTF16_LE, 'utf-16-le'),
            (codecs.BOM_UTF16_BE, 'utf-16-be'),
            (codecs.BOM_UTF32_LE, 'utf-32-le'),
            (codecs.BOM_UTF32_BE, 'utf-32-be'),
        ):
            with self.subTest(encoding=encoding):
                with patch('components.knowledge_engine.parser.chardet.detect') as detect:
                    parsed = await parser.parse(prefix + text.encode(encoding), 'conversation.txt')

                self.assertEqual(parsed, text)
                detect.assert_not_called()

    async def test_unmarked_unicode_with_nuls_uses_encoding_detection(self):
        text = 'Meeting at 10 today.'
        parser = FileParser()

        for encoding in ('utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be'):
            with self.subTest(encoding=encoding):
                with patch(
                    'components.knowledge_engine.parser.chardet.detect',
                    return_value={'encoding': encoding, 'confidence': 0.9},
                ) as detect:
                    raw = text.encode(encoding)
                    parsed = await parser.parse(raw, 'conversation.txt')

                self.assertEqual(parsed, text)
                detect.assert_called_once_with(raw)

    async def test_legacy_encoding_uses_detection_after_utf8_fails(self):
        text = 'My friend’s café is nearby.'
        raw = text.encode('cp1252')
        parser = FileParser()

        with patch(
            'components.knowledge_engine.parser.chardet.detect',
            return_value={'encoding': 'Windows-1252', 'confidence': 0.73},
        ) as detect:
            parsed = await parser.parse(raw, 'conversation.txt')

        self.assertEqual(parsed, text)
        detect.assert_called_once_with(raw)
