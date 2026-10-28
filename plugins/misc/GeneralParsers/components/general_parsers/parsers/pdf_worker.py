"""PyMuPDF extraction executed inside the isolated worker process.

This module is imported **only** by
:mod:`components.general_parsers.process_worker`; the shared runtime process
never imports it, so PyMuPDF's module-level page state (``EDGES`` / ``CHARS`` in
``pymupdf.table``) exists per parse and is destroyed with the worker.

The whole synchronous lifecycle - open the document, collect font/header/footer
metadata, detect tables, extract table content, extract text and images, close
the document - happens inside a single call in a single process, which is what
makes the dependency safe to use from a multi-tenant worker.
"""

from __future__ import annotations

import hashlib
import logging
import statistics
from collections import Counter
from typing import Any

try:  # PyMuPDF >= 1.24 exposes the modern import name
    import pymupdf as fitz
except ImportError:  # pragma: no cover - legacy alias only
    import fitz

from ..utils import count_words, strip_page_markers
from ..vision import encode_image_base64

logger = logging.getLogger(__name__)

# B4: Font-size heading thresholds (ratio relative to median font size)
_HEADING_RATIO_H1 = 2.0
_HEADING_RATIO_H2 = 1.6
_HEADING_RATIO_H3 = 1.3
_HEADING_MAX_LINE_LEN = 100  # lines longer than this are unlikely headings


def extract_pdf(file_bytes: bytes, collect_vision_tasks: bool) -> dict[str, Any]:
    """Extract text, metadata and pending vision tasks from PDF bytes.

    Args:
        file_bytes: Raw PDF bytes.
        collect_vision_tasks: Whether the caller can process vision tasks; when
            true, base64 payloads for scanned pages and embedded images are
            collected. When false they are left out (off by default in the
            shared runtime where no vision model is configured).

    Returns:
        ``{'text': str, 'metadata': dict, 'vision_tasks': list}``.
    """
    page_count = 0
    page_texts: list[str] = []
    images: list[dict] = []
    scanned_pages: list[int] = []
    has_tables = False
    vision_tasks: list[dict] = []
    headers_footers_removed = False
    baseline_font_size = 12.0

    with fitz.open(stream=file_bytes, filetype='pdf') as doc:
        page_count = len(doc)

        # B4: Collect all font sizes across the document for median computation
        all_font_sizes: list[float] = []

        # B2: Collect candidate header/footer texts per page
        # Structure: { text: count }
        top_texts: Counter = Counter()
        bottom_texts: Counter = Counter()
        page_top_bottom: list[tuple[list[str], list[str]]] = []

        # --- First pass: collect font sizes and header/footer candidates ---
        for page in doc:
            page_rect = page.rect
            page_height = page_rect.height
            top_threshold = page_rect.y0 + page_height * 0.05
            bottom_threshold = page_rect.y1 - page_height * 0.05

            text_dict = page.get_text('dict', flags=fitz.TEXT_PRESERVE_WHITESPACE)
            page_top: list[str] = []
            page_bottom: list[str] = []

            for block in text_dict.get('blocks', []):
                if block['type'] != 0:
                    continue
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        size = span.get('size', 0)
                        if size > 0:
                            all_font_sizes.append(size)

                    # B2: Check if line is in top or bottom margin
                    line_bbox = line.get('bbox', (0, 0, 0, 0))
                    line_y_center = (line_bbox[1] + line_bbox[3]) / 2
                    line_text = ''.join(
                        span['text'] for span in line.get('spans', [])
                    ).strip()

                    if line_text and len(line_text) < 80:
                        if line_y_center < top_threshold:
                            page_top.append(line_text)
                            top_texts[line_text] += 1
                        elif line_y_center > bottom_threshold:
                            page_bottom.append(line_text)
                            bottom_texts[line_text] += 1

            page_top_bottom.append((page_top, page_bottom))

        # B4: Compute baseline (median) font size
        baseline_font_size = statistics.median(all_font_sizes) if all_font_sizes else 12.0

        # B2: Determine header/footer patterns (appear on > 50% of pages)
        min_occurrences = max(2, page_count * 0.5)
        header_patterns: set[str] = set()
        footer_patterns: set[str] = set()
        for text, count in top_texts.items():
            if count >= min_occurrences:
                header_patterns.add(text)
        for text, count in bottom_texts.items():
            if count >= min_occurrences:
                footer_patterns.add(text)

        headers_footers_removed = bool(header_patterns or footer_patterns)
        if headers_footers_removed:
            logger.info(
                f'Detected {len(header_patterns)} header and '
                f'{len(footer_patterns)} footer patterns to filter'
            )

        # --- Second pass: extract content per page ---
        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            page_rect = page.rect
            page_height = page_rect.height
            page_width = page_rect.width
            page_area = page_height * page_width

            # B2: Get this page's header/footer texts to filter
            page_header_texts, page_footer_texts = page_top_bottom[page_idx]
            filter_texts = set()
            for t in page_header_texts:
                if t in header_patterns:
                    filter_texts.add(t)
            for t in page_footer_texts:
                if t in footer_patterns:
                    filter_texts.add(t)

            # --- Collect table regions to avoid duplicating table text ---
            tables = page.find_tables()
            if tables:
                has_tables = True
            table_rects = []
            table_entries = []  # (y0, x0, markdown_str)
            for table in tables:
                bbox = fitz.Rect(table.bbox)
                table_rects.append(bbox)
                md = _pymupdf_table_to_markdown(table)
                if md:
                    table_entries.append((bbox.y0, bbox.x0, md))

            # --- Extract text blocks with position info ---
            text_dict = page.get_text('dict', flags=fitz.TEXT_PRESERVE_WHITESPACE)
            text_entries = []  # (y0, x0, text_str)
            for block in text_dict.get('blocks', []):
                if block['type'] != 0:  # skip image blocks
                    continue
                block_rect = fitz.Rect(block['bbox'])

                # Skip text blocks that overlap significantly with a table region
                in_table = False
                for tr in table_rects:
                    overlap = block_rect & tr  # intersection
                    if not overlap.is_empty and overlap.height > block_rect.height * 0.5:
                        in_table = True
                        break
                if in_table:
                    continue

                lines_text = []
                for line in block.get('lines', []):
                    spans_text = ''.join(span['text'] for span in line.get('spans', []))
                    stripped = spans_text.strip()
                    if not stripped:
                        continue

                    # B2: Skip header/footer text
                    if stripped in filter_texts:
                        continue

                    # B4: Font-size heading heuristics
                    if len(stripped) < _HEADING_MAX_LINE_LEN:
                        line_sizes = [
                            span['size'] for span in line.get('spans', [])
                            if span.get('size', 0) > 0
                        ]
                        if line_sizes:
                            avg_size = sum(line_sizes) / len(line_sizes)
                            ratio = avg_size / baseline_font_size if baseline_font_size > 0 else 1.0
                            if ratio >= _HEADING_RATIO_H1:
                                stripped = f'# {stripped}'
                            elif ratio >= _HEADING_RATIO_H2:
                                stripped = f'## {stripped}'
                            elif ratio >= _HEADING_RATIO_H3:
                                stripped = f'### {stripped}'

                    lines_text.append(stripped)
                if lines_text:
                    text_entries.append((block['bbox'][1], block['bbox'][0], '\n'.join(lines_text)))

            # --- Merge text and table entries by vertical position ---
            all_entries = []
            for y0, x0, text in text_entries:
                all_entries.append((y0, x0, 'text', text))
            for y0, x0, md in table_entries:
                all_entries.append((y0, x0, 'table', md))
            all_entries.sort(key=lambda e: (e[0], e[1]))

            page_parts = []
            for _, _, kind, content in all_entries:
                if kind == 'table':
                    page_parts.append('\n' + content + '\n')
                else:
                    page_parts.append(content)

            # --- Extract images ---
            page_images = page.get_images(full=True)
            for img_idx, img_info in enumerate(page_images):
                xref = img_info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    # Convert CMYK / other color spaces to RGB
                    if pix.n - pix.alpha > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_bytes = pix.tobytes('png')
                    images.append({
                        'page': page_num,
                        'index': img_idx,
                        'width': pix.width,
                        'height': pix.height,
                        'format': 'png',
                        'sha256': hashlib.sha256(img_bytes).hexdigest(),
                        'size_bytes': len(img_bytes),
                    })
                    placeholder = f'[图片: 第{page_num}页-图片{img_idx + 1}]'
                    page_parts.append(placeholder)
                    # Collect embedded image vision task
                    if collect_vision_tasks:
                        vision_tasks.append({
                            'type': 'embedded_image',
                            'page': page_num,
                            'img_idx': img_idx,
                            'image_b64': encode_image_base64(img_bytes),
                            'placeholder': placeholder,
                        })
                except Exception as e:
                    logger.warning(f'Failed to extract image xref={xref} on page {page_num}: {e}')

            # --- B1: Improved scanned page detection ---
            plain_text = page.get_text('text').strip()
            text_len = len(plain_text)
            page_has_images = len(page_images) > 0

            # Compute image area ratio for B1
            image_area_ratio = 0.0
            if page_has_images and page_area > 0:
                total_img_area = 0.0
                for img_info in page_images:
                    xref = img_info[0]
                    try:
                        img_rects = page.get_image_rects(xref)
                        for rect in img_rects:
                            total_img_area += rect.width * rect.height
                    except Exception:
                        pass
                image_area_ratio = total_img_area / page_area

            # Three-condition OR logic for scanned page detection
            is_scanned = False
            if text_len < 30 and page_has_images:
                is_scanned = True
            elif image_area_ratio > 0.8 and text_len < 100:
                is_scanned = True
            elif page_has_images and page_area > 0:
                text_density = text_len / page_area
                if text_density < 0.001 and text_len < 200:
                    is_scanned = True

            if is_scanned:
                scanned_pages.append(page_num)

            # Render scanned page to image for vision OCR
            if is_scanned and collect_vision_tasks:
                try:
                    pix = page.get_pixmap(dpi=200)
                    page_img_bytes = pix.tobytes('png')
                    vision_tasks.append({
                        'type': 'scanned_page',
                        'page': page_num,
                        'image_b64': encode_image_base64(page_img_bytes),
                    })
                except Exception as e:
                    logger.warning(f'Failed to render scanned page {page_num}: {e}')

            if page_parts:
                page_texts.append(f'<!-- PAGE:{page_num} -->\n' + '\n'.join(page_parts))

    full_text = '\n\n'.join(page_texts)
    extra_metadata = {
        'page_count': page_count,
        'word_count': count_words(strip_page_markers(full_text)),
        'has_tables': has_tables,
        'has_scanned_pages': bool(scanned_pages),
    }
    if scanned_pages:
        extra_metadata['scanned_pages'] = scanned_pages
    if images:
        extra_metadata['images'] = images
    if headers_footers_removed:
        extra_metadata['headers_footers_removed'] = True

    return {
        'text': full_text,
        'metadata': extra_metadata,
        'vision_tasks': vision_tasks,
    }


def _pymupdf_table_to_markdown(table) -> str:
    """Convert a PyMuPDF Table object into a Markdown table string."""
    data = table.extract()
    if not data:
        return ''

    # Clean cell values: replace None with empty string, strip whitespace
    cleaned = []
    for row in data:
        cleaned.append([str(cell).strip() if cell is not None else '' for cell in row])

    if not cleaned:
        return ''

    # First row as header
    header = cleaned[0]
    lines = [
        '| ' + ' | '.join(header) + ' |',
        '| ' + ' | '.join(['---'] * len(header)) + ' |',
    ]
    for row in cleaned[1:]:
        # Pad or trim row to match header length
        padded = row + [''] * (len(header) - len(row)) if len(row) < len(header) else row[:len(header)]
        lines.append('| ' + ' | '.join(padded) + ' |')

    return '\n'.join(lines)
