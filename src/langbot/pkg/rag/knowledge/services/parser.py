from __future__ import annotations

import PyPDF2
import io
from docx import Document
import chardet
from typing import Union, Callable, Any
import markdown
from bs4 import BeautifulSoup
import re
import asyncio  # Import asyncio for async operations
from langbot.pkg.core import app


class FileParser:
    """
    A robust file parser class to extract text content from various document formats.
    It supports TXT, PDF, DOCX, XLSX, CSV, Markdown, HTML, and EPUB files.
    All core file reading operations are designed to be run synchronously in a thread pool
    to avoid blocking the asyncio event loop.
    """

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def _run_sync(self, sync_func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Runs a synchronous function in a separate thread to prevent blocking the event loop.
        This is a general utility method for wrapping blocking I/O operations.
        """
        try:
            return await asyncio.to_thread(sync_func, *args, **kwargs)
        except Exception as e:
            self.ap.logger.error(f'Error running synchronous function {sync_func.__name__}: {e}')
            raise

    async def parse(self, file_name: str, extension: str) -> Union[str, None]:
        """
        Parses the file based on its extension and returns the extracted text content.
        This is the main asynchronous entry point for parsing.

        Args:
            file_name (str): The name of the file to be parsed, get from ap.storage_mgr

        Returns:
            Union[str, None]: The extracted text content as a single string, or None if parsing fails.
        """

        file_extension = extension.lower()
        parser_method = getattr(self, f'_parse_{file_extension}', None)

        if parser_method is None:
            self.ap.logger.error(f'Unsupported file format: {file_extension} for file {file_name}')
            return None

        try:
            # Pass file_path to the specific parser methods
            return await parser_method(file_name)
        except Exception as e:
            self.ap.logger.error(f'Failed to parse {file_extension} file {file_name}: {e}')
            return None

    # --- Helper for reading files with encoding detection ---
    async def _read_file_content(self, file_name: str) -> Union[str, bytes]:
        """
        Reads a file with automatic encoding detection, ensuring the synchronous
        file read operation runs in a separate thread.
        """

        # def _read_sync():
        #     with open(file_path, 'rb') as file:
        #         raw_data = file.read()
        #         detected = chardet.detect(raw_data)
        #         encoding = detected['encoding'] or 'utf-8'

        #     if mode == 'r':
        #         return raw_data.decode(encoding, errors='ignore')
        #     return raw_data  # For binary mode

        # return await self._run_sync(_read_sync)
        file_bytes = await self.ap.storage_mgr.storage_provider.load(file_name)

        detected = chardet.detect(file_bytes)
        encoding = detected['encoding'] or 'utf-8'

        return file_bytes.decode(encoding, errors='ignore')

    # --- Specific Parser Methods ---

    async def _parse_txt(self, file_name: str) -> str:
        """Parses a TXT file and returns its content."""
        self.ap.logger.info(f'Parsing TXT file: {file_name}')
        return await self._read_file_content(file_name)

    async def _parse_pdf(self, file_name: str) -> str:
        """Parses a PDF file and returns its text content."""
        self.ap.logger.info(f'Parsing PDF file: {file_name}')

        # def _parse_pdf_sync():
        #     text_content = []
        #     with open(file_name, 'rb') as file:
        #         pdf_reader = PyPDF2.PdfReader(file)
        #         for page in pdf_reader.pages:
        #             text = page.extract_text()
        #             if text:
        #                 text_content.append(text)
        #     return '\n'.join(text_content)

        # return await self._run_sync(_parse_pdf_sync)

        pdf_bytes = await self.ap.storage_mgr.storage_provider.load(file_name)

        def _parse_pdf_sync():
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text_content = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
            return '\n'.join(text_content)

        return await self._run_sync(_parse_pdf_sync)

    async def _parse_docx(self, file_name: str) -> str:
        """Parses a DOCX file and returns its text content."""
        self.ap.logger.info(f'Parsing DOCX file: {file_name}')

        docx_bytes = await self.ap.storage_mgr.storage_provider.load(file_name)

        def _parse_docx_sync():
            doc = Document(io.BytesIO(docx_bytes))
            text_content = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
            return '\n'.join(text_content)

        return await self._run_sync(_parse_docx_sync)

    async def _parse_doc(self, file_name: str) -> str:
        """Handles .doc files, explicitly stating lack of direct support."""
        self.ap.logger.warning(f'Direct .doc parsing is not supported for {file_name}. Please convert to .docx first.')
        raise NotImplementedError('Direct .doc parsing not supported. Please convert to .docx first.')

    # async def _parse_xlsx(self, file_name: str) -> str:
    #     """Parses an XLSX file, returning text from all sheets."""
    #     self.ap.logger.info(f'Parsing XLSX file: {file_name}')

    #     xlsx_bytes = await self.ap.storage_mgr.storage_provider.load(file_name)

    #     def _parse_xlsx_sync():
    #         excel_file = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    #         all_sheet_content = []
    #         for sheet_name in excel_file.sheet_names:
    #             df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=sheet_name)
    #             sheet_text = f'--- Sheet: {sheet_name} ---\n{df.to_string(index=False)}\n'
    #             all_sheet_content.append(sheet_text)
    #         return '\n'.join(all_sheet_content)

    #     return await self._run_sync(_parse_xlsx_sync)

    # async def _parse_csv(self, file_name: str) -> str:
    #     """Parses a CSV file and returns its content as a string."""
    #     self.ap.logger.info(f'Parsing CSV file: {file_name}')

    #     csv_bytes = await self.ap.storage_mgr.storage_provider.load(file_name)

    #     def _parse_csv_sync():
    #         # pd.read_csv can often detect encoding, but explicit detection is safer
    #         # raw_data = self._read_file_content(
    #         #     file_name, mode='rb'
    #         # )  # Note: this will need to be await outside this sync function
    #         # _ = raw_data
    #         # For simplicity, we'll let pandas handle encoding internally after a raw read.
    #         # A more robust solution might pass encoding directly to pd.read_csv after detection.
    #         detected = chardet.detect(io.BytesIO(csv_bytes))
    #         encoding = detected['encoding'] or 'utf-8'
    #         df = pd.read_csv(io.BytesIO(csv_bytes), encoding=encoding)
    #         return df.to_string(index=False)

    #     return await self._run_sync(_parse_csv_sync)

    async def _parse_md(self, file_name: str) -> str:
        """Parses a Markdown file, converting it to structured plain text."""
        self.ap.logger.info(f'Parsing Markdown file: {file_name}')

        md_bytes = await self.ap.storage_mgr.storage_provider.load(file_name)

        def _parse_markdown_sync():
            md_content = io.BytesIO(md_bytes).read().decode('utf-8', errors='ignore')
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
                    table_str = self._extract_table_to_markdown_sync(element)  # Call sync helper
                    if table_str:
                        text_parts.append(table_str)
                elif element.name:
                    text = element.get_text(separator=' ', strip=True)
                    if text:
                        text_parts.append(text)
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', '\n'.join(text_parts))
            return cleaned_text.strip()

        return await self._run_sync(_parse_markdown_sync)

    async def _parse_html(self, file_name: str) -> str:
        """Parses an HTML file, extracting structured plain text."""
        self.ap.logger.info(f'Parsing HTML file: {file_name}')

        html_bytes = await self.ap.storage_mgr.storage_provider.load(file_name)

        def _parse_html_sync():
            html_content = io.BytesIO(html_bytes).read().decode('utf-8', errors='ignore')
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
                    table_str = self._extract_table_to_markdown_sync(element)  # Call sync helper
                    if table_str:
                        text_parts.append(table_str)
                elif element.name:
                    text = element.get_text(separator=' ', strip=True)
                    if text:
                        text_parts.append(text)
            cleaned_text = re.sub(r'\n\s*\n', '\n\n', '\n'.join(text_parts))
            return cleaned_text.strip()

        return await self._run_sync(_parse_html_sync)

    def _add_toc_items_sync(self, toc_list: list, text_content: list, level: int):
        """Recursively adds TOC items to text_content (synchronous helper)."""
        indent = '  ' * level
        for item in toc_list:
            if isinstance(item, tuple):
                chapter, subchapters = item
                text_content.append(f'{indent}- {chapter.title}')
                self._add_toc_items_sync(subchapters, text_content, level + 1)
            else:
                text_content.append(f'{indent}- {item.title}')

    def _extract_table_to_markdown_sync(self, table_element: BeautifulSoup) -> str:
        """Helper to convert a BeautifulSoup table element into a Markdown table string (synchronous)."""
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
