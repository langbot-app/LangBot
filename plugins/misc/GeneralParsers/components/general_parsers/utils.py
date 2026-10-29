from __future__ import annotations

import asyncio
import re
from typing import Callable, Any

import chardet

_PAGE_MARKER_RE = re.compile(r'<!-- PAGE:\d+ -->\n?')
_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
_CJK_CHAR_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\U00020000-\U0002a6df\U0002a700-\U0002b73f"
    r"\U0002b740-\U0002b81f\U0002b820-\U0002ceaf]"
)


def decode_text(file_bytes: bytes) -> str:
    """Decode bytes to text with conservative encoding detection."""
    for encoding in ('utf-8', 'utf-8-sig'):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            pass

    detected = chardet.detect(file_bytes)
    encoding = detected.get('encoding')
    confidence = detected.get('confidence') or 0
    if encoding and confidence >= 0.6:
        return file_bytes.decode(encoding, errors='ignore')

    for encoding in ('gb18030', 'gbk', 'big5'):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            pass

    return file_bytes.decode(encoding or 'utf-8', errors='ignore')


def count_words(text: str) -> int:
    """Count Latin words and CJK characters as searchable text units."""
    if not text:
        return 0
    return len(_LATIN_WORD_RE.findall(text)) + len(_CJK_CHAR_RE.findall(text))


def strip_page_markers(text: str) -> str:
    """Remove the ``<!-- PAGE:N -->`` markers the PDF parser emits."""
    return _PAGE_MARKER_RE.sub('', text)


def config_bool(value: Any) -> bool:
    """Parse bool-like config values from UI/plugin configs."""
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}
    return bool(value)


def find_page(position: int, page_positions: list[tuple[int, int]]) -> int | None:
    """Find which page a text position belongs to.

    page_positions is a sorted list of (char_position, page_number).
    Returns the page number for the largest marker position <= the given position.
    """
    result = None
    for pos, page in page_positions:
        if pos <= position:
            result = page
        else:
            break
    return result


async def run_sync(sync_func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Run a synchronous function in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(sync_func, *args, **kwargs)
