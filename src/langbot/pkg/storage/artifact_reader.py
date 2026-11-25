"""Bounded model-facing reads of already-authorized Artifact bytes."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import re

from ..i18n import t
from .artifacts import ArtifactError, MAX_ARTIFACT_BYTES


MAX_TEXT_CHARS = 16384
MAX_PDF_PAGES = 10
MAX_PDF_EXTRACTED_CHARS = 1024 * 1024
MAX_PDF_STREAM_BYTES = 2 * 1024 * 1024


def _unsupported(message: str):
    return ArtifactError('artifact_read_unsupported', t(message), 415)


def _text_result(metadata: dict, mode: str, **result) -> list[dict]:
    public = {
        key: metadata[key] for key in ('id', 'ref', 'name', 'mime_type', 'size', 'digest', 'source') if key in metadata
    }
    return [{'type': 'text', 'text': json.dumps({'artifact': public, 'mode': mode, **result}, ensure_ascii=False)}]


def _slice(text: str, offset: int, max_chars: int) -> dict:
    if offset > len(text):
        raise ValueError('Artifact offset exceeds the text length')
    end = min(len(text), offset + max_chars)
    return {
        'offset': offset,
        'end_offset': end,
        'total_chars': len(text),
        'truncated': end < len(text),
        'next_offset': end if end < len(text) else None,
        'text': text[offset:end],
    }


def _parse_pdf(content: bytes, page_start: int, page_end: int | None, *, extract_text: bool) -> tuple[str, dict]:
    from pypdf import PdfReader, apply_configuration
    from pypdf.errors import PdfReadError

    # pypdf's ContextVar scopes decoding and parsing budgets to this read, including nested forms.
    with apply_configuration(
        maximum_declared_stream_length=MAX_PDF_STREAM_BYTES,
        array_based_stream_maximum_output_length=MAX_PDF_STREAM_BYTES,
        array_maximum_element_count=10000,
        dictionary_maximum_element_count=10000,
        zlib_maximum_output_length=MAX_PDF_STREAM_BYTES,
        lzw_maximum_output_length=MAX_PDF_STREAM_BYTES,
        run_length_maximum_output_length=MAX_PDF_STREAM_BYTES,
        brotli_maximum_output_length=MAX_PDF_STREAM_BYTES,
        jbig2_maximum_output_length=MAX_PDF_STREAM_BYTES,
        image_maximum_buffer_size=MAX_PDF_STREAM_BYTES,
        stream_decoding_work_maximum_length=4 * MAX_PDF_STREAM_BYTES,
        stream_parsing_work_maximum_count=100000,
        stream_filters_maximum_length=8,
        flate_maximum_columns=10000,
        flate_maximum_row_length=65536,
        page_tree_maximum_entries=1000,
        page_tree_maximum_depth=32,
        xform_maximum_invocations_per_extraction=100,
        jbig2dec_binary=None,
        disable_legacy_handling=True,
    ):
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise PdfReadError('Encrypted PDF')
        page_count = len(reader.pages)
        if not page_count:
            raise PdfReadError('PDF has no pages')
        if not extract_text:
            # Check the native file structure and page tree, but do not extract
            # text or rasterize images before passing the document to the model.
            return '', {}
        if page_start > page_count:
            raise ArtifactError('invalid_input', 'PDF page_start exceeds the page count', 400)
        last_page = min(page_start + MAX_PDF_PAGES - 1, page_count) if page_end is None else page_end
        if last_page > page_count:
            raise ArtifactError('invalid_input', 'PDF page_end exceeds the page count', 400)
        parts = []
        chars = 0
        for index in range(page_start - 1, last_page):
            page = reader.pages[index]
            text = page.extract_text() or ''
            chars += len(text)
            if chars > MAX_PDF_EXTRACTED_CHARS:
                raise ArtifactError('artifact_too_large', t('PDF text extraction exceeds the size limit.'), 413)
            parts.append(f'[Page {index + 1}]\n{text}')
        return '\n\n'.join(parts), {
            'page_start': page_start,
            'page_end': last_page,
            'page_count': page_count,
            'next_page': last_page + 1 if last_page < page_count else None,
            'text_only': True,
            'notice': t(
                'PDF text extraction excludes images and page layout. Use native mode with a supported model for visual content.'
            ),
        }


def _read_pdf(content: bytes, page_start: int, page_end: int | None, *, extract_text: bool = True) -> tuple[str, dict]:
    from pypdf.errors import LimitReachedError, PdfReadError

    try:
        return _parse_pdf(content, page_start, page_end, extract_text=extract_text)
    except (LimitReachedError, MemoryError) as exc:
        raise ArtifactError('artifact_too_large', t('PDF text extraction exceeds the size limit.'), 413) from exc
    except (PdfReadError, NotImplementedError, KeyError, TypeError, ValueError, IndexError, RecursionError) as exc:
        raise ArtifactError(
            'artifact_pdf_unreadable',
            t('The PDF could not be read. It may be malformed or password-protected.'),
            422,
        ) from exc


def _image_mime(content: bytes) -> str | None:
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if content.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if content.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        return 'image/webp'
    return None


async def read_artifact_content(
    content: bytes,
    metadata: dict,
    *,
    mode: str = 'auto',
    offset: int = 0,
    max_chars: int = 8192,
    page_start: int = 1,
    page_end: int | None = None,
) -> list[dict]:
    """Read text ranges or return structured image/native-PDF input after authorization."""
    if not isinstance(content, bytes) or len(content) > MAX_ARTIFACT_BYTES:
        raise ValueError('Artifact content must be bytes within the 10 MiB limit')
    if not isinstance(mode, str) or mode not in {'auto', 'text', 'native', 'pages'}:
        raise ValueError('Artifact mode must be auto, text, native or pages')
    if type(offset) is not int or offset < 0:
        raise ValueError('Artifact offset must be a non-negative character index')
    if type(max_chars) is not int or not 1 <= max_chars <= MAX_TEXT_CHARS:
        raise ValueError('Artifact max_chars must be between 1 and 16384')
    if type(page_start) is not int or page_start < 1:
        raise ValueError('PDF page_start must be a positive page number')
    if page_end is not None and (
        type(page_end) is not int or page_end < page_start or page_end - page_start >= MAX_PDF_PAGES
    ):
        raise ValueError('PDF page range must contain between 1 and 10 pages')
    mime_type = metadata.get('mime_type') or 'application/octet-stream'
    is_pdf = content.lstrip(b'\r\n\t ').startswith(b'%PDF-')
    if mode == 'pages':
        raise _unsupported('PDF page rendering is unavailable. Use text extraction or a model with native PDF support.')
    image_mime = _image_mime(content)
    if image_mime and mode in {'auto', 'native'}:
        if offset or page_start != 1 or page_end is not None:
            raise ValueError('Image reads do not accept text offsets or PDF page ranges')
        return _text_result(metadata, 'image') + [
            {
                'type': 'image_base64',
                'image_base64': f'data:{image_mime};base64,' + base64.b64encode(content).decode('ascii'),
            }
        ]
    if is_pdf or mime_type == 'application/pdf':
        if not is_pdf:
            raise ArtifactError(
                'artifact_pdf_unreadable',
                t('The PDF could not be read. It may be malformed or password-protected.'),
                422,
            )
        if mode == 'native':
            if offset or page_start != 1 or page_end is not None:
                raise ValueError('Native PDF mode reads the complete document, without text offsets or page ranges')
            await asyncio.to_thread(_read_pdf, content, page_start, page_end, extract_text=False)
            return _text_result(metadata, 'native') + [
                {
                    'type': 'file_base64',
                    'file_name': metadata.get('name') or 'document.pdf',
                    'file_base64': 'data:application/pdf;base64,' + base64.b64encode(content).decode('ascii'),
                }
            ]
        text, pages = await asyncio.to_thread(_read_pdf, content, page_start, page_end)
        return _text_result(metadata, 'text', **pages, **_slice(text, offset, max_chars))
    if mode == 'native' or image_mime:
        raise _unsupported('This file type cannot be read by the model. Download the original file instead.')
    if page_start != 1 or page_end is not None:
        raise ValueError('PDF page ranges cannot be used with a text file')
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise _unsupported('This file type cannot be read by the model. Download the original file instead.') from exc
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', text):
        raise _unsupported('This file type cannot be read by the model. Download the original file instead.')
    return _text_result(metadata, 'text', **_slice(text, offset, max_chars))
