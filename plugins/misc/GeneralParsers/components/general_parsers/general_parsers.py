from __future__ import annotations

import re
import logging
import time
from importlib import import_module
from typing import Any
from .utils import config_bool, decode_text, find_page
from ..observability import get_telemetry

from langbot_plugin.api.definition.components.parser.parser import Parser
from langbot_plugin.api.entities.builtin.rag.models import (
    ParseContext,
    ParseResult,
    TextSection,
)


logger = logging.getLogger(__name__)

PARSERS = {
    'pdf': '.parsers.pdf:parse_pdf',
    'docx': '.parsers.docx:parse_docx',
    'doc': None,  # not supported
    'txt': '.parsers.html_text:parse_txt',
    'md': '.parsers.html_text:parse_md',
    'html': '.parsers.html_text:parse_html',
    'htm': '.parsers.html_text:parse_html',
    'png': '.parsers.image:parse_image',
    'jpg': '.parsers.image:parse_image',
    'jpeg': '.parsers.image:parse_image',
    'webp': '.parsers.image:parse_image',
    'gif': '.parsers.image:parse_image',
    'bmp': '.parsers.image:parse_image',
    'tif': '.parsers.image:parse_image',
    'tiff': '.parsers.image:parse_image',
}

VISION_AWARE_EXTENSIONS = {
    'pdf',
    'docx',
    'md',
    'html',
    'htm',
    'png',
    'jpg',
    'jpeg',
    'webp',
    'gif',
    'bmp',
    'tif',
    'tiff',
}

MIME_EXTENSION_FALLBACK = {
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'text/plain': 'txt',
    'text/markdown': 'md',
    'text/html': 'html',
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/webp': 'webp',
    'image/gif': 'gif',
    'image/bmp': 'bmp',
    'image/tiff': 'tiff',
}


def _filename_extension(filename: str) -> str:
    if '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[-1].lower()


def _select_extension(filename: str, mime_type: str) -> tuple[str, str, str | None]:
    filename_extension = _filename_extension(filename)
    mime_extension = MIME_EXTENSION_FALLBACK.get(mime_type, '')
    if mime_extension:
        warning = None
        if (
            filename_extension
            and filename_extension in PARSERS
            and filename_extension != mime_extension
        ):
            warning = (
                f"filename extension '{filename_extension}' conflicts with "
                f"MIME type '{mime_type}', using MIME-derived '{mime_extension}'"
            )
        return mime_extension, 'mime_type', warning
    if filename_extension:
        return filename_extension, 'filename', None
    return '', 'unknown', None


def _load_parser(parser_ref: str):
    module_name, attr_name = parser_ref.split(':', 1)
    module = import_module(module_name, package=__package__)
    return getattr(module, attr_name)


class GeneralParsers(Parser):
    """GeneralParsers component that extracts structured text from binary files.

    Supports PDF, DOCX, Markdown, HTML, plain text, and direct image files.
    Based on the parsing logic from LangRAG.
    """

    async def parse(self, context: ParseContext) -> ParseResult:
        """Parse a file and extract structured text.

        Args:
            context: Contains file_content (bytes), mime_type, filename, and metadata.

        Returns:
            ParseResult with extracted text and optional structured sections.
        """
        started_at = time.perf_counter()
        binding = self.get_installation_binding()
        filename = context.filename
        raw_mime_type = context.mime_type
        mime_type = (raw_mime_type or '').split(';', 1)[0].strip().lower()
        extension = ''
        extension_source = 'unknown'
        text_for_telemetry = ''
        sections_for_telemetry: list[Any] = []
        metadata_for_telemetry: dict[str, Any] = {}
        raised_error: Exception | None = None

        try:
            file_bytes = context.file_content
            extension, extension_source, extension_warning = _select_extension(
                filename,
                mime_type,
            )

            # Build invoke_vision callback if a vision model is configured
            invoke_vision = None
            config = self.plugin.get_config() or {}
            vision_enabled = config_bool(config.get('enable_vision'))
            vision_model_uuid = config.get('vision_llm_model_uuid') if vision_enabled else None
            if vision_model_uuid:
                async def invoke_vision(image_b64: str, prompt: str) -> str:
                    from langbot_plugin.api.entities.builtin.provider.message import (
                        Message, ContentElement,
                    )
                    resp = await self.plugin.invoke_llm(
                        vision_model_uuid,
                        [Message(role='user', content=[
                            ContentElement.from_image_base64(image_b64),
                            ContentElement.from_text(prompt),
                        ])],
                        timeout=60,
                    )
                    if isinstance(resp.content, str):
                        return resp.content
                    return ''.join(
                        e.text for e in resp.content if e.type == 'text' and e.text
                    )

            extra_metadata = {}
            if extension in PARSERS:
                parser_ref = PARSERS[extension]
                if parser_ref is None:
                    logger.warning(f'Unsupported file format: {extension} for {filename}')
                    text = ''
                else:
                    try:
                        parser_func = _load_parser(parser_ref)
                        if extension in VISION_AWARE_EXTENSIONS:
                            result = await parser_func(file_bytes, filename, invoke_vision=invoke_vision)
                        else:
                            result = await parser_func(file_bytes, filename)
                        # Parsers may return (text, extra_metadata) or plain text only.
                        if isinstance(result, tuple):
                            text, extra_metadata = result
                        else:
                            text = result
                    except Exception as e:
                        logger.error(f'Failed to parse {extension} file {filename}: {e}')
                        extra_metadata = {
                            'parser_failed': True,
                            'parse_error': str(e),
                        }
                        text = None
            else:
                logger.warning(f'Unsupported file format: {extension} for {filename}, trying as text')
                text = decode_text(file_bytes)

            if text is None:
                text = ''

            sections = self._split_sections(text, filename, track_pages=(extension == 'pdf'))

            # Strip page markers from the text output
            if extension == 'pdf':
                text = re.sub(r'<!-- PAGE:\d+ -->\n?', '', text)

            metadata = {
                'filename': filename,
                'mime_type': context.mime_type,
                'extension': extension,
                'extension_source': extension_source,
            }
            if extension_warning:
                metadata['extension_warning'] = extension_warning
            metadata.update(extra_metadata)

            text_for_telemetry = text
            sections_for_telemetry = sections
            metadata_for_telemetry = metadata

            return ParseResult(
                text=text,
                sections=sections,
                metadata=metadata,
            )
        except Exception as e:
            raised_error = e
            metadata_for_telemetry = {
                'filename': filename,
                'mime_type': raw_mime_type,
                'extension': extension,
                'extension_source': extension_source,
                'parser_failed': True,
                'parse_error': str(e),
            }
            raise
        finally:
            try:
                get_telemetry(binding).record_parse(
                    filename=filename,
                    mime_type=raw_mime_type,
                    extension=extension,
                    extension_source=extension_source,
                    duration_ms=(time.perf_counter() - started_at) * 1000,
                    text_chars=len(text_for_telemetry or ''),
                    sections_count=len(sections_for_telemetry or []),
                    metadata=metadata_for_telemetry,
                    failed=raised_error is not None,
                    parse_error=str(raised_error) if raised_error is not None else None,
                )
            except Exception as telemetry_error:
                logger.warning(f'Failed to record parser telemetry: {telemetry_error}')

    # ========== Section Extraction ==========

    @staticmethod
    def _split_sections(text: str, filename: str, track_pages: bool = False) -> list[TextSection]:
        """Split text into sections based on heading patterns.

        Supports Markdown headings, Chinese chapter/section numbering,
        numeric outlines (1. / 1.1 / 1.1.1), and English chapter/section labels.

        If track_pages is True, extracts page markers (<!-- PAGE:N -->) from the text
        and assigns page numbers to each section.
        """
        if not text:
            return []

        # Extract page markers and build position→page mapping, then strip markers
        _PAGE_MARKER_RE = re.compile(r'<!-- PAGE:(\d+) -->\n?')
        page_positions = []  # sorted list of (position_in_clean_text, page_number)
        if track_pages:
            # Build mapping from clean-text positions to page numbers
            offset = 0  # cumulative chars removed by stripping markers
            for m in _PAGE_MARKER_RE.finditer(text):
                clean_pos = m.start() - offset
                page_positions.append((clean_pos, int(m.group(1))))
                offset += len(m.group(0))
            text = _PAGE_MARKER_RE.sub('', text)

        # Each pattern: (compiled regex, level_func(match) -> int, heading_func(match) -> str)
        heading_patterns = [
            # Markdown: # ~ ######
            (
                re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE),
                lambda m: len(m.group(1)),
                lambda m: m.group(2).strip(),
            ),
            # 第一章/第1章/第一篇/第一部
            (
                re.compile(r'^第[一二三四五六七八九十百千\d]+[章篇部]\s*(.+)$', re.MULTILINE),
                lambda m: 1,
                lambda m: m.group(0).strip(),
            ),
            # 第一节
            (
                re.compile(r'^第[一二三四五六七八九十百千\d]+[节]\s*(.+)$', re.MULTILINE),
                lambda m: 2,
                lambda m: m.group(0).strip(),
            ),
            # 1.1.1 xxx (check before 1.1 and 1.)
            (
                re.compile(r'^(\d+\.\d+\.\d+)\s+(.+)$', re.MULTILINE),
                lambda m: 3,
                lambda m: m.group(0).strip(),
            ),
            # 1.1 xxx
            (
                re.compile(r'^(\d+\.\d+)\s+(.+)$', re.MULTILINE),
                lambda m: 2,
                lambda m: m.group(0).strip(),
            ),
            # 1. xxx (top-level numbered)
            (
                re.compile(r'^(\d+)\.\s+(.+)$', re.MULTILINE),
                lambda m: 1,
                lambda m: m.group(0).strip(),
            ),
            # Chapter 1: xxx / CHAPTER I: xxx
            (
                re.compile(r'^(?:Chapter|CHAPTER)\s+\w+\s*[.:：]\s*(.+)$', re.MULTILINE),
                lambda m: 1,
                lambda m: m.group(0).strip(),
            ),
            # Section 1: xxx / SECTION 1: xxx
            (
                re.compile(r'^(?:Section|SECTION)\s+\w+\s*[.:：]\s*(.+)$', re.MULTILINE),
                lambda m: 2,
                lambda m: m.group(0).strip(),
            ),
            # Article 1: xxx / ARTICLE 1: xxx
            (
                re.compile(r'^(?:Article|ARTICLE)\s+\w+\s*[.:：]\s*(.+)$', re.MULTILINE),
                lambda m: 2,
                lambda m: m.group(0).strip(),
            ),
        ]

        # Collect all heading matches: (start, end, level, heading_text)
        all_matches = []
        for pattern, level_func, heading_func in heading_patterns:
            for m in pattern.finditer(text):
                all_matches.append((m.start(), m.end(), level_func(m), heading_func(m)))

        if not all_matches:
            return [
                TextSection(
                    content=text,
                    heading=filename,
                    level=0,
                    page=page_positions[0][1] if page_positions else None,
                )
            ]

        # Sort by position in text; for overlapping matches keep the earliest/longest
        all_matches.sort(key=lambda x: (x[0], -x[1]))

        # Deduplicate overlapping matches: if two matches overlap, keep the first one
        deduped = []
        last_end = -1
        for start, end, level, heading in all_matches:
            if start >= last_end:
                deduped.append((start, end, level, heading))
                last_end = end

        sections = []
        for i, (start, end, level, heading) in enumerate(deduped):
            content_start = end
            content_end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
            body = text[content_start:content_end].strip()
            content = f'{heading}\n{body}' if body else heading
            if content:
                page = find_page(start, page_positions) if page_positions else None
                sections.append(
                    TextSection(
                        content=content,
                        heading=heading,
                        level=level,
                        page=page,
                    )
                )

        # Include text before first heading if any
        preamble = text[: deduped[0][0]].strip()
        if preamble:
            page = find_page(0, page_positions) if page_positions else None
            sections.insert(
                0,
                TextSection(
                    content=preamble,
                    heading=filename,
                    level=0,
                    page=page,
                ),
            )

        return sections
