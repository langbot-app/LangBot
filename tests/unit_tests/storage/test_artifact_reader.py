"""Model-facing ranges, media inputs and real PDF decoding budgets."""

import base64
import io
import json

from PIL import Image, ImageChops
import pytest
from pypdf import PdfReader, PdfWriter, get_configuration
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from langbot.pkg.storage.artifact_reader import MAX_PDF_PAGES, MAX_PDF_STREAM_BYTES, read_artifact_content
from langbot.pkg.storage.artifacts import ArtifactError, MAX_ARTIFACT_BYTES
from tests.utils.artifact_media import make_artifact_media, text_pdf


pytestmark = pytest.mark.asyncio
_META = {'id': 'art_test', 'name': 'reference.txt', 'mime_type': 'text/plain', 'content_ref': 'private-key'}


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


async def test_media_fixtures_have_stable_bytes_without_markers_in_metadata():
    first = make_artifact_media('chat-one')
    second = make_artifact_media('chat-two')
    assert first == make_artifact_media('chat-one')
    assert [sample.filename for sample in first] == [sample.filename for sample in second]
    assert len({sample.marker for sample in (*first, *second)}) == 8
    for a, b in zip(first, second, strict=True):
        assert a.sha256 != b.sha256 and 0 < a.size < MAX_ARTIFACT_BYTES
        assert a.marker not in (a.filename + a.mime_type)
        assert a.marker.encode() not in a.data
        if a.kind in {'png', 'jpeg'}:
            with Image.open(io.BytesIO(a.data)) as image_a, Image.open(io.BytesIO(b.data)) as image_b:
                assert image_a.format == image_b.format == a.kind.upper()
                assert image_a.size == image_b.size == (480, 160)
                assert a.marker not in repr(image_a.info)
                assert ImageChops.difference(image_a, image_b).getbbox() is not None
        else:
            reader = PdfReader(io.BytesIO(a.data), strict=True)
            assert a.marker not in repr(reader.metadata)
            assert len(reader.pages) == 1
            page = reader.pages[0]
            if a.kind == 'text_pdf':
                assert page.extract_text().strip() == a.marker
                assert not page.images
            else:
                assert not page.extract_text().strip()
                assert len(page.images) == 1
                other_page = PdfReader(io.BytesIO(b.data), strict=True).pages[0]
                assert ImageChops.difference(page.images[0].image, other_page.images[0].image).getbbox() is not None


async def test_images_and_native_pdf_remain_structured_instead_of_textual_base64():
    for media in make_artifact_media('structured-inputs'):
        is_pdf = media.mime_type == 'application/pdf'
        result = await read_artifact_content(
            media.data, {'name': media.filename, 'mime_type': media.mime_type}, mode='native'
        )
        assert len(result) == 2
        assert _text(result)['mode'] == ('native' if is_pdf else 'image')
        kind = 'file_base64' if is_pdf else 'image_base64'
        assert result[1]['type'] == kind
        if is_pdf:
            assert result[1]['file_name'] == media.filename
        mime, b64 = result[1][kind].split(',', 1)
        assert mime == f'data:{media.mime_type};base64'
        assert base64.b64decode(b64, validate=True) == media.data
        assert b64 not in result[0]['text']
        assert media.marker not in result[0]['text']


async def test_image_read_mode_reports_detected_mime_and_disallows_text_mode():
    png = make_artifact_media('mismatched-image')[0]
    declared = {'name': 'claimed.jpg', 'mime_type': 'image/jpeg'}
    image = await read_artifact_content(png.data, declared)
    assert _text(image)['artifact']['mime_type'] == 'image/jpeg'
    assert image[1]['image_base64'].startswith('data:image/png;base64,')
    with pytest.raises(ArtifactError) as failure:
        await read_artifact_content(png.data, declared, mode='text')
    assert failure.value.error_code == 'artifact_read_unsupported' and failure.value.status_code == 415


async def test_text_mode_exposes_selectable_text_but_never_claims_ocr():
    _, _, selectable, scanned = make_artifact_media('extract-text')
    for media in (selectable, scanned):
        result = await read_artifact_content(media.data, {'mime_type': media.mime_type}, mode='text')
        assert len(result) == 1
        payload = _text(result)
        assert payload['text_only'] is True
        assert 'excludes images' in payload['notice'] and 'native mode' in payload['notice']
        if media.kind == 'scanned_pdf':
            assert payload['text'] == '[Page 1]\n'
            assert media.marker not in payload['text']
        else:
            assert payload['text'].strip() == f'[Page 1]\n{media.marker}'


async def test_pdf_and_byte_boundaries_preserve_bounded_continuation():
    last_page = MAX_PDF_PAGES + 1
    pages = text_pdf(*(f'Document page {number}' for number in range(1, last_page + 1)))
    first = _text(await read_artifact_content(pages, {}))
    assert first['page_end'] == MAX_PDF_PAGES and first['next_page'] == last_page
    assert f'[Page {last_page}]' not in first['text']
    last = _text(await read_artifact_content(pages, {}, page_start=last_page))
    assert last['text'].strip() == f'[Page {last_page}]\nDocument page {last_page}'
    assert last['next_page'] is None
    with pytest.raises(ValueError, match='page range'):
        await read_artifact_content(pages, {}, page_end=last_page)
    with pytest.raises(ArtifactError) as failure:
        await read_artifact_content(pages, {}, page_start=last_page + 1)
    assert failure.value.error_code == 'invalid_input' and failure.value.status_code == 400
    data = b'a' * MAX_ARTIFACT_BYTES
    limited = _text(await read_artifact_content(data, _META, max_chars=10))
    assert limited['total_chars'] == MAX_ARTIFACT_BYTES and limited['next_offset'] == 10
    assert limited['text'] == 'a' * 10
    with pytest.raises(ValueError, match='10 MiB'):
        await read_artifact_content(data + b'a', _META)


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
    valid_pdf = text_pdf('Authenticated content')
    for content in (
        b'non-PDF bytes declared as PDF',
        b'%PDF-broken',
        valid_pdf[:-45],
        _pdf('Protected', encrypted=True),
        _pdf(),
    ):
        for mode in ('auto', 'native', 'text'):
            with pytest.raises(ArtifactError) as failure:
                await read_artifact_content(content, {'mime_type': 'application/pdf'}, mode=mode)
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
