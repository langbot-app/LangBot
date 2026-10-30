from __future__ import annotations

import base64
import hashlib
import io
import re
import logging
from typing import Optional

from docx import Document
from docx.oxml.ns import qn

from ..utils import count_words, run_sync
from ..vision import ANALYZE_IMAGE_PROMPT, InvokeVision, sanitize_vision_text

logger = logging.getLogger(__name__)


async def parse_docx(
    file_bytes: bytes,
    filename: str,
    invoke_vision: Optional[InvokeVision] = None,
) -> tuple[str, dict]:
    """Parse DOCX with table extraction, heading styles, list recognition,
    and document-flow-order output.

    Returns:
        A tuple of (text, extra_metadata).
    """
    logger.info(f'Parsing DOCX file: {filename}')

    def _sync():
        from docx.table import Table as DocxTable
        from docx.text.paragraph import Paragraph

        doc = Document(io.BytesIO(file_bytes))
        parts = []
        has_tables = False
        images = []
        vision_tasks = []
        image_index = 0

        for block in doc.element.body:
            tag = block.tag

            if tag.endswith('}p'):
                para = Paragraph(block, doc)
                para_parts = []
                text = para.text.strip()

                if text:
                    style_name = para.style.name if para.style else ''

                    # Heading recognition: "Heading 1" through "Heading 6"
                    heading_match = re.match(r'Heading\s*(\d+)', style_name, re.IGNORECASE)
                    if heading_match:
                        level = min(int(heading_match.group(1)), 6)
                        para_parts.append('#' * level + ' ' + text)
                    elif 'List' in style_name:
                        para_parts.append('* ' + text)
                    else:
                        para_parts.append(text)

                for run in para.runs:
                    blips = run._element.findall(
                        './/{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
                    )
                    for blip in blips:
                        rel_id = blip.get(qn('r:embed'))
                        if not rel_id:
                            continue
                        try:
                            image_part = doc.part.related_parts[rel_id]
                            img_bytes = image_part.blob
                            image_index += 1
                            img_b64 = base64.b64encode(img_bytes).decode('ascii')
                            placeholder = f'[图片: 文档图片{image_index}]'
                            para_parts.append(placeholder)
                            images.append({
                                'index': image_index,
                                'content_type': getattr(image_part, 'content_type', ''),
                                'sha256': hashlib.sha256(img_bytes).hexdigest(),
                                'size_bytes': len(img_bytes),
                            })
                            if invoke_vision is not None:
                                vision_tasks.append({
                                    'placeholder': placeholder,
                                    'image_b64': img_b64,
                                })
                        except Exception as e:
                            logger.warning(f'Failed to extract DOCX image rel_id={rel_id}: {e}')

                if para_parts:
                    parts.append('\n'.join(para_parts))

            elif tag.endswith('}tbl'):
                has_tables = True
                try:
                    table = DocxTable(block, doc)
                    md = _docx_table_to_markdown(table)
                    if md:
                        parts.append('\n' + md + '\n')
                except Exception as e:
                    logger.warning(f'Failed to extract DOCX table: {e}')

        full_text = '\n'.join(parts)
        extra_metadata = {
            'word_count': count_words(full_text),
            'has_tables': has_tables,
            'has_images': bool(images),
        }
        if images:
            extra_metadata['images'] = images
            extra_metadata['images_count'] = len(images)
        return full_text, extra_metadata, vision_tasks
    full_text, extra_metadata, vision_tasks = await run_sync(_sync)

    if invoke_vision is not None and vision_tasks:
        described_count = 0
        failed_count = 0
        for task in vision_tasks:
            try:
                raw_vision_text = await invoke_vision(task['image_b64'], ANALYZE_IMAGE_PROMPT)
            except Exception as e:
                logger.warning(f'DOCX image vision call failed: {e}')
                failed_count += 1
                continue
            vision_text = sanitize_vision_text(raw_vision_text)
            if not vision_text:
                continue
            full_text = full_text.replace(task['placeholder'], f'[图片描述: {vision_text}]', 1)
            described_count += 1

        extra_metadata['vision_used'] = described_count > 0
        extra_metadata['vision_tasks_count'] = len(vision_tasks)
        extra_metadata['vision_images_described_count'] = described_count
        extra_metadata['vision_failed_count'] = failed_count
        extra_metadata['word_count'] = count_words(full_text)
    elif invoke_vision is not None:
        extra_metadata['vision_used'] = False

    return full_text, extra_metadata


def _docx_table_to_markdown(table) -> str:
    """Convert a python-docx Table object into a Markdown table string."""
    rows_data = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        rows_data.append(cells)

    if not rows_data:
        return ''

    # First row as header
    header = rows_data[0]
    col_count = len(header)
    lines = [
        '| ' + ' | '.join(header) + ' |',
        '| ' + ' | '.join(['---'] * col_count) + ' |',
    ]
    for row in rows_data[1:]:
        padded = row + [''] * (col_count - len(row)) if len(row) < col_count else row[:col_count]
        lines.append('| ' + ' | '.join(padded) + ' |')

    return '\n'.join(lines)
