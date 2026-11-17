"""Model-facing ranges, media inputs and real PDF decoding budgets."""

import base64
import io
import json

import pytest
from pypdf import PdfWriter, get_configuration
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from langbot.pkg.storage.artifact_reader import MAX_PDF_STREAM_BYTES, read_artifact_content
from langbot.pkg.storage.artifacts import ArtifactError


pytestmark = pytest.mark.asyncio
_META = {'id': 'art_test', 'name': 'reference.txt', 'mime_type': 'text/plain', 'content_ref': 'private-key'}
_PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII=')


def _pdf(*texts, encrypted=False, compressed_payload=None):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'),
                NameObject('/BaseFont'): NameObject('/Helvetica'),
            }
        )
        page[NameObject('/Resources')] = DictionaryObject(
            {
                NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)}),
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(
            compressed_payload
            if compressed_payload is not None
            else (f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode('ascii'))
        )
        page[NameObject('/Contents')] = writer._add_object(
            stream.flate_encode() if compressed_payload is not None else stream
        )
    if encrypted:
        writer.encrypt('password')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _text(elements):
    assert elements[0]['type'] == 'text'
    return json.loads(elements[0]['text'])


async def test_text_ranges_use_characters_and_preserve_exact_resume_position():
    result = _text(await read_artifact_content('a猫🙂z'.encode(), _META, offset=1, max_chars=2))
    assert result['text'] == '猫🙂'
    assert (result['offset'], result['end_offset'], result['total_chars']) == (1, 3, 4)
    assert result['truncated'] is True and result['next_offset'] == 3
    assert 'content_ref' not in result['artifact']
    remainder = _text(await read_artifact_content('a猫🙂z'.encode(), _META, offset=3))
    assert remainder['text'] == 'z' and remainder['next_offset'] is None
    assert remainder['truncated'] is False


async def test_images_and_native_pdf_remain_structured_instead_of_textual_base64():
    image = await read_artifact_content(_PNG, {'name': 'pixel.png', 'mime_type': 'image/png'})
    assert _text(image)['mode'] == 'image'
    assert len(image) == 2 and image[1]['type'] == 'image_base64'
    assert base64.b64decode(image[1]['image_base64'].split(',', 1)[1], validate=True) == _PNG
    assert 'base64' not in image[0]['text']
    pdf = _pdf('Native file payload')
    native = await read_artifact_content(pdf, {'name': None}, mode='native')
    assert _text(native)['mode'] == 'native'
    assert native[1]['type'] == 'file_base64' and native[1]['file_name'] == 'document.pdf'
    assert base64.b64decode(native[1]['file_base64'].split(',', 1)[1], validate=True) == pdf


async def test_pdf_selected_pages_and_text_limits_report_continuation_and_visual_boundary():
    content = _pdf('First page original', 'Second page original', 'Third page original')
    result = _text(await read_artifact_content(content, {'mime_type': 'application/pdf'}, page_start=2, page_end=2))
    assert 'Second page original' in result['text']
    assert 'First page original' not in result['text'] and 'Third page original' not in result['text']
    assert (result['page_start'], result['page_end'], result['page_count'], result['next_page']) == (2, 2, 3, 3)
    assert result['text_only'] is True and 'excludes images' in result['notice']
    limited = _text(await read_artifact_content(content, {}, max_chars=4, page_end=1))
    assert limited['text'] == '[Pag' and limited['truncated'] is True and limited['next_offset'] == 4


async def test_compressed_pdf_is_rejected_before_unbounded_expansion_and_configuration_is_restored():
    content = _pdf('', compressed_payload=b' ' * (MAX_PDF_STREAM_BYTES + 1))
    assert len(content) < 10000
    original = get_configuration()
    with pytest.raises(ArtifactError) as failure:
        await read_artifact_content(content, {})
    assert failure.value.error_code == 'artifact_too_large' and failure.value.status_code == 413
    assert get_configuration() is original
    assert 'ordinary PDF' in _text(await read_artifact_content(_pdf('ordinary PDF'), {}))['text']


async def test_unreadable_pdf_and_unsupported_formats_fail_explicitly():
    for content in (b'%PDF-broken', _pdf('Protected', encrypted=True)):
        with pytest.raises(ArtifactError) as failure:
            await read_artifact_content(content, {'mime_type': 'application/pdf'})
        assert failure.value.error_code == 'artifact_pdf_unreadable' and failure.value.status_code == 422
    for content, options in ((b'\x00binary', {}), (_pdf('Text'), {'mode': 'pages'})):
        with pytest.raises(ArtifactError) as failure:
            await read_artifact_content(content, {}, **options)
        assert failure.value.error_code == 'artifact_read_unsupported' and failure.value.status_code == 415


@pytest.mark.parametrize(
    'options',
    [
        {'mode': []},
        {'offset': True},
        {'offset': -1},
        {'max_chars': True},
        {'max_chars': 16385},
        {'page_start': False},
        {'page_start': 0},
        {'page_end': True},
        {'page_end': 11},
    ],
)
async def test_read_arguments_reject_invalid_ranges_and_boolean_numbers(options):
    with pytest.raises(ValueError):
        await read_artifact_content(b'text', _META, **options)
