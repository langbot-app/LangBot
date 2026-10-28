from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..isolated_process import DEFAULT_TIMEOUT_SECONDS, run_isolated
from ..utils import count_words, strip_page_markers
from ..vision import (
    ANALYZE_IMAGE_PROMPT,
    OCR_PAGE_PROMPT,
    InvokeVision,
    sanitize_vision_text,
)

logger = logging.getLogger(__name__)

#: Hard lifetime bound for the worker process that performs a single PDF parse.
PDF_PARSE_TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
#: Worker entry point, resolved inside the isolated process.
PDF_WORKER_REFERENCE = f'{__package__}.pdf_worker:extract_pdf'


async def parse_pdf(
    file_bytes: bytes,
    filename: str,
    invoke_vision: Optional[InvokeVision] = None,
) -> tuple[str, dict]:
    """Parse PDF using PyMuPDF with table extraction, image extraction, and position-aware text.

    The PyMuPDF work runs in a dedicated short-lived process (see
    :mod:`..isolated_process`): PyMuPDF is not thread safe and its table finder
    keeps module-level page state, so parsing it from the shared worker's thread
    pool could mix one installation's page text into another's result or crash
    the shared process. Everything from opening the document to closing it
    happens inside that one process, and the worker is torn down before this
    coroutine returns - including on timeout and on cancellation.

    Enhancements over the basic version:
    - B1: Improved scanned page detection (text amount + image area ratio + text density)
    - B2: Header/footer detection and filtering
    - B3: Vision call statistics in metadata
    - B4: Font-size based heading heuristics (injects Markdown ``#`` markers)

    Args:
        file_bytes: Raw PDF bytes.
        filename: Original filename.
        invoke_vision: Optional async callable ``(image_base64, prompt) -> str``.
            When provided, scanned pages are OCR'd and embedded images are described
            via a vision-capable LLM.

    Returns:
        A tuple of (text, extra_metadata) where extra_metadata contains extracted images.
    """
    logger.info(f'Parsing PDF file: {filename}')

    extracted = await run_isolated(
        PDF_WORKER_REFERENCE,
        file_bytes,
        invoke_vision is not None,
        timeout=PDF_PARSE_TIMEOUT_SECONDS,
        name='PDF parse',
    )
    full_text = extracted['text']
    extra_metadata = extracted['metadata']
    vision_tasks = extracted['vision_tasks']

    # --- Async vision processing ---
    vision_stats = {}
    if invoke_vision is not None and vision_tasks:
        full_text, vision_stats = await _process_vision_tasks(full_text, vision_tasks, invoke_vision)
        extra_metadata['word_count'] = count_words(strip_page_markers(full_text))

    # B3: Vision call statistics
    if vision_tasks:
        extra_metadata['vision_tasks_count'] = len(vision_tasks)
        extra_metadata.setdefault('vision_scanned_pages_count', 0)
        extra_metadata.setdefault('vision_images_described_count', 0)
        extra_metadata.setdefault('vision_failed_count', 0)
        extra_metadata.update(vision_stats)
        extra_metadata['vision_used'] = (
            extra_metadata['vision_scanned_pages_count']
            + extra_metadata['vision_images_described_count']
        ) > 0
    elif invoke_vision is not None:
        extra_metadata['vision_used'] = False

    return full_text, extra_metadata


async def _process_vision_tasks(
    full_text: str,
    vision_tasks: list[dict],
    invoke_vision: InvokeVision,
) -> tuple[str, dict]:
    """Concurrently invoke the vision model for scanned pages and embedded images,
    then replace placeholders in the text with the results."""
    semaphore = asyncio.Semaphore(5)
    stats = {
        'vision_scanned_pages_count': 0,
        'vision_images_described_count': 0,
        'vision_failed_count': 0,
    }

    async def _call_vision(task: dict) -> tuple[dict, str, bool]:
        async with semaphore:
            try:
                if task['type'] == 'scanned_page':
                    prompt = OCR_PAGE_PROMPT
                else:
                    prompt = ANALYZE_IMAGE_PROMPT
                result = await invoke_vision(task['image_b64'], prompt)
                return task, result, False
            except Exception as e:
                logger.warning(f'Vision call failed for {task["type"]} page={task["page"]}: {e}')
                return task, '', True

    results = await asyncio.gather(*[_call_vision(t) for t in vision_tasks])

    for task, vision_text, failed in results:
        if failed:
            stats['vision_failed_count'] += 1
            continue
        vision_text = sanitize_vision_text(vision_text)
        if not vision_text:
            continue

        if task['type'] == 'scanned_page':
            # Replace the scanned page's content (between PAGE marker and next marker/end)
            page_num = task['page']
            marker = f'<!-- PAGE:{page_num} -->\n'
            marker_pos = full_text.find(marker)
            if marker_pos == -1:
                # Page had no content at all — insert it
                # Find the right insertion point by looking for adjacent page markers
                prev_marker = f'<!-- PAGE:{page_num - 1} -->'
                next_marker = f'<!-- PAGE:{page_num + 1} -->'
                prev_pos = full_text.find(prev_marker)
                next_pos = full_text.find(next_marker)

                new_page_block = f'<!-- PAGE:{page_num} -->\n{vision_text}'
                if next_pos != -1:
                    full_text = full_text[:next_pos] + new_page_block + '\n\n' + full_text[next_pos:]
                elif prev_pos != -1:
                    # Insert after the previous page block
                    # Find end of previous page block (next double newline or end)
                    block_end = full_text.find('\n\n', prev_pos)
                    if block_end == -1:
                        full_text = full_text + '\n\n' + new_page_block
                    else:
                        full_text = full_text[:block_end] + '\n\n' + new_page_block + full_text[block_end:]
                else:
                    full_text = new_page_block + '\n\n' + full_text if full_text else new_page_block
            else:
                # Replace existing (mostly empty) page content
                content_start = marker_pos + len(marker)
                # Find the next page marker or end of text
                next_page_pos = full_text.find('\n\n<!-- PAGE:', content_start)
                if next_page_pos == -1:
                    content_end = len(full_text)
                else:
                    content_end = next_page_pos

                full_text = full_text[:content_start] + vision_text + full_text[content_end:]
            stats['vision_scanned_pages_count'] += 1

        elif task['type'] == 'embedded_image':
            placeholder = task['placeholder']
            replacement = f'[图片描述: {vision_text}]'
            full_text = full_text.replace(placeholder, replacement, 1)
            stats['vision_images_described_count'] += 1

    return full_text, stats
