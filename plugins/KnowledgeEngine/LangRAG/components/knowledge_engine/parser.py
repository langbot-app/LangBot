"""DEPRECATED: Internal file parser — fallback only.

This parser provides basic text extraction for cases where no external Parser
plugin (e.g. GeneralParsers) is configured.  It lacks section splitting,
metadata extraction, table-aware chunking, and many other features available
in GeneralParsers.

New features should NOT be added here.  Instead, invest in GeneralParsers
or a dedicated parser plugin.  This module will be removed in a future
version once external parser adoption is widespread.
"""

from __future__ import annotations

import io
import re
from components.offload import BoundedOffload
import logging
from typing import Union, Callable, Any

import chardet


logger = logging.getLogger(__name__)


class FileParser:
    """
    A robust file parser class to extract text content from various document formats.
    It supports TXT, PDF, DOCX, Markdown, HTML files.

    This version is designed to work in the Plugin environment, accepting file bytes
    directly rather than relying on Host's storage manager.
    """

    def __init__(self, offload=None):
        self.offload = offload or BoundedOffload()

    async def _run_sync(self, sync_func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Runs a synchronous function in a separate thread to prevent blocking the event loop.
        """
        try:
            return await self.offload.run(sync_func, *args, **kwargs)
        except Exception as e:
            logger.error(f'Error running synchronous function {sync_func.__name__}: {e}')
            raise

    async def parse(self, file_bytes: bytes, filename: str) -> Union[str, None]:
        """
        Parses the file based on its extension and returns the extracted text content.

        Args:
            file_bytes: The raw bytes of the file content.
            filename: The name of the file (used to determine extension).

        Returns:
            Union[str, None]: The extracted text content as a single string, or None if parsing fails.
        """
        if len(file_bytes) > 16 * 1024 * 1024:
            raise ValueError("File exceeds the 16 MiB internal parser limit")
        # Extract extension from filename
        if '.' in filename:
            file_extension = filename.rsplit('.', 1)[-1].lower()
        else:
            file_extension = ''

        parser_method = getattr(self, f'_parse_{file_extension}', None)

        if parser_method is None:
            logger.warning(f'Unsupported file format: {file_extension} for file {filename}, trying as text')
            # Fallback: try to decode as text
            return await self._run_sync(self._decode_text, file_bytes)

        try:
            return await parser_method(file_bytes, filename)
        except Exception as e:
            logger.error(f'Failed to parse {file_extension} file {filename}: {e}')
            return None

    def _decode_text(self, file_bytes: bytes) -> str:
        """Decode bytes to text with encoding detection."""
        detected = chardet.detect(file_bytes)
        encoding = detected['encoding'] or 'utf-8'
        return file_bytes.decode(encoding, errors='ignore')

    # --- Specific Parser Methods ---

    async def _parse_txt(self, file_bytes: bytes, filename: str) -> str:
        """Parses a TXT file and returns its content."""
        logger.info(f'Parsing TXT file: {filename}')
        return await self._run_sync(self._decode_text, file_bytes)

    async def _parse_pdf(self, file_bytes: bytes, filename: str) -> str:
        """Parses a PDF file and returns its text content."""
        logger.info(f'Parsing PDF file: {filename}')

        def _parse_pdf_sync():
            import PyPDF2

            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text_content = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
            return '\n'.join(text_content)

        return await self._run_sync(_parse_pdf_sync)

    async def _parse_docx(self, file_bytes: bytes, filename: str) -> str:
        """Parses a DOCX file and returns its text content."""
        logger.info(f'Parsing DOCX file: {filename}')

        def _parse_docx_sync():
            from docx import Document

            doc = Document(io.BytesIO(file_bytes))
            text_content = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
            return '\n'.join(text_content)

        return await self._run_sync(_parse_docx_sync)

    async def _parse_doc(self, file_bytes: bytes, filename: str) -> str:
        """Handles .doc files, explicitly stating lack of direct support."""
        logger.warning(f'Direct .doc parsing is not supported for {filename}. Please convert to .docx first.')
        raise NotImplementedError('Direct .doc parsing not supported. Please convert to .docx first.')

    async def _parse_md(self, file_bytes: bytes, filename: str) -> str:
        """Parses a Markdown file, converting it to structured plain text."""
        logger.info(f'Parsing Markdown file: {filename}')

        def _parse_markdown_sync():
            import markdown
            from bs4 import BeautifulSoup

            md_content = file_bytes.decode('utf-8', errors='ignore')
            html_content = markdown.markdown(
                md_content, extensions=['extra', 'codehilite', 'tables', 'toc', 'fenced_code']
            )
            soup = BeautifulSoup(html_content, 'html.parser')
            text_parts = []
            for element in soup.children:
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    level = int(element.name[1])
                    text_parts.append('#' * level + ' ' + element.get_text().strip())
                elif element.name == 'p':
                    text = element.get_text().strip()
                    if text:
                        text_parts.append(text)
                elif element.name in ['ul', 'ol']:
                    for li in element.find_all('li'):
                        text_parts.append(f'* {li.get_text().strip()}')
                elif element.name == 'pre':
                    code_block = element.get_text().strip()
                    if code_block:
                        text_parts.append(f'```\n{code_block}\n```')
                elif element.name == 'table':
                    table_str = self._extract_table_to_markdown_sync(element)
                    if table_str:
                        text_parts.append(table_str)
                elif element.name:
                    text = element.get_text(separator=' ', strip=True)
                    if text:
                        text_parts.append(text)
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', '\n'.join(text_parts))
            return cleaned_text.strip()

        return await self._run_sync(_parse_markdown_sync)

    async def _parse_html(self, file_bytes: bytes, filename: str) -> str:
        """Parses an HTML file, extracting structured plain text."""
        logger.info(f'Parsing HTML file: {filename}')

        def _parse_html_sync():
            from bs4 import BeautifulSoup

            html_content = file_bytes.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html_content, 'html.parser')
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()
            text_parts = []
            for element in soup.body.children if soup.body else soup.children:
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    level = int(element.name[1])
                    text_parts.append('#' * level + ' ' + element.get_text().strip())
                elif element.name == 'p':
                    text = element.get_text().strip()
                    if text:
                        text_parts.append(text)
                elif element.name in ['ul', 'ol']:
                    for li in element.find_all('li'):
                        text = li.get_text().strip()
                        if text:
                            text_parts.append(f'* {text}')
                elif element.name == 'table':
                    table_str = self._extract_table_to_markdown_sync(element)
                    if table_str:
                        text_parts.append(table_str)
                elif element.name:
                    text = element.get_text(separator=' ', strip=True)
                    if text:
                        text_parts.append(text)
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', '\n'.join(text_parts))
            return cleaned_text.strip()

        return await self._run_sync(_parse_html_sync)

    def _extract_table_to_markdown_sync(self, table_element) -> str:
        """Helper to convert a BeautifulSoup table element into a Markdown table string."""
        headers = [th.get_text().strip() for th in table_element.find_all('th')]
        rows = []
        for tr in table_element.find_all('tr'):
            cells = [td.get_text().strip() for td in tr.find_all('td')]
            if cells:
                rows.append(cells)

        if not headers and not rows:
            return ''

        table_lines = []
        if headers:
            table_lines.append(' | '.join(headers))
            table_lines.append(' | '.join(['---'] * len(headers)))

        for row_cells in rows:
            padded_cells = row_cells + [''] * (len(headers) - len(row_cells)) if headers else row_cells
            table_lines.append(' | '.join(padded_cells))

        return '\n'.join(table_lines)
