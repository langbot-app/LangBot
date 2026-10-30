"""Text chunking utilities using recursive character splitting.

Extracted from langrag.py to allow reuse across different index strategies.
Also provides section-aware chunking that preserves document structure.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50

# Separators in order of semantic significance (paragraph → sentence → word → char)
_SEPARATORS = [
    "\n\n",  # Paragraphs
    "\n",    # Lines
    ". ",    # Sentences
    "。",    # Chinese/Japanese sentence end
    "! ",    # Exclamations
    "? ",    # Questions
    "; ",    # Semicolons
    "；",    # Chinese semicolon
    "，",    # Chinese comma
    ", ",    # Commas
    " ",     # Spaces (words)
    "",      # Characters (fallback)
]


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping chunks using recursive character splitting.

    Attempts to split at natural semantic boundaries (paragraphs, sentences,
    words) before falling back to character-level splitting. This preserves
    readability and context compared to a naive sliding-window approach.

    Args:
        text: The text to split.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of overlapping characters between consecutive chunks.

    Returns:
        List of text chunks.
    """
    if not text:
        return []

    if chunk_overlap >= chunk_size:
        logger.warning(
            f"chunk_overlap ({chunk_overlap}) >= chunk_size ({chunk_size}), "
            "clamping overlap to chunk_size - 1"
        )
        chunk_overlap = chunk_size - 1

    return _split_recursive(text, _SEPARATORS, chunk_size, chunk_overlap)


def _split_recursive(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Recursively split *text* trying each separator in priority order."""
    final_chunks: list[str] = []
    separator = separators[0] if separators else ""
    remaining_separators = separators[1:] if len(separators) > 1 else []

    splits = _split_by_separator(text, separator)

    current_parts: list[str] = []
    current_len = 0

    for part in splits:
        part_len = len(part)

        # Single piece already exceeds limit → recurse with finer separator
        if part_len > chunk_size:
            # Flush accumulated parts first
            if current_parts:
                final_chunks.append("".join(current_parts))
                current_parts = _overlap_parts(current_parts, chunk_overlap)
                current_len = sum(len(p) for p in current_parts)

            if remaining_separators:
                final_chunks.extend(
                    _split_recursive(part, remaining_separators, chunk_size, chunk_overlap)
                )
            else:
                final_chunks.extend(_split_by_char(part, chunk_size, chunk_overlap))
            continue

        # Would adding this part exceed the limit?
        if current_parts and current_len + part_len > chunk_size:
            final_chunks.append("".join(current_parts))
            current_parts = _overlap_parts(current_parts, chunk_overlap)
            current_len = sum(len(p) for p in current_parts)

        current_parts.append(part)
        current_len += part_len

    if current_parts:
        final_chunks.append("".join(current_parts))

    return final_chunks


def _split_by_separator(text: str, separator: str) -> list[str]:
    """Split *text* by *separator*, keeping the separator attached to the left piece."""
    if separator == "":
        return list(text)

    parts = text.split(separator)
    result: list[str] = []
    for piece in parts[:-1]:
        if piece or separator.strip():
            result.append(piece + separator)
    if parts[-1]:
        result.append(parts[-1])
    return result


def _overlap_parts(parts: list[str], overlap: int) -> list[str]:
    """Return trailing *parts* whose combined length fits within *overlap*."""
    if overlap <= 0:
        return []

    kept: list[str] = []
    total = 0
    for part in reversed(parts):
        if total + len(part) > overlap:
            break
        kept.insert(0, part)
        total += len(part)
    return kept


def _split_by_char(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Last-resort character-level split."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Section-aware chunking
# ---------------------------------------------------------------------------

# Regex matching a contiguous block of Markdown table rows (|...|)
_TABLE_LINE_RE = re.compile(r"^(\|.+\|)\s*$")


@dataclass
class SectionChunk:
    """A chunk derived from a structured section, carrying structural metadata."""

    text: str
    heading: str | None = None
    level: int = 0
    page: int | None = None
    heading_path: str = ""
    has_table: bool = False
    section_index: int = 0


def chunk_sections(
    sections: list,
    chunk_size: int,
    chunk_overlap: int,
) -> list[SectionChunk]:
    """Split structured sections into chunks while preserving heading/page metadata.

    Each section is chunked independently.  Short sections (≤ *chunk_size*)
    become a single chunk; long sections are split internally using
    table-aware logic that avoids breaking Markdown tables.

    Args:
        sections: List of TextSection objects (from ParseResult).
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks within a section.

    Returns:
        List of :class:`SectionChunk` instances.
    """
    if not sections:
        return []

    heading_paths = _compute_heading_paths(sections)
    result: list[SectionChunk] = []

    for sec_idx, section in enumerate(sections):
        content = section.content
        if not content or not content.strip():
            continue

        heading = getattr(section, "heading", None)
        level = getattr(section, "level", 0)
        page = getattr(section, "page", None)
        h_path = heading_paths[sec_idx] if sec_idx < len(heading_paths) else ""

        sub_chunks = _split_section_content(content, chunk_size, chunk_overlap)

        for sc_text, sc_has_table in sub_chunks:
            result.append(
                SectionChunk(
                    text=sc_text,
                    heading=heading,
                    level=level,
                    page=page,
                    heading_path=h_path,
                    has_table=sc_has_table,
                    section_index=sec_idx,
                )
            )

    return result


def _compute_heading_paths(sections: list) -> list[str]:
    """Compute hierarchical heading paths for each section using a stack.

    For example, if sections have headings at levels:
        [("Chapter 1", 1), ("1.1 Overview", 2), ("1.2 Details", 2), ("Chapter 2", 1)]
    the paths would be:
        ["Chapter 1", "Chapter 1 > 1.1 Overview", "Chapter 1 > 1.2 Details", "Chapter 2"]
    """
    stack: list[tuple[int, str]] = []  # (level, heading)
    paths: list[str] = []

    for section in sections:
        heading = getattr(section, "heading", None) or ""
        level = getattr(section, "level", 0)

        # Pop entries at same or deeper level
        while stack and stack[-1][0] >= level:
            stack.pop()

        stack.append((level, heading))
        paths.append(" > ".join(h for _, h in stack if h))

    return paths


def _segment_text_and_tables(content: str) -> list[tuple[str, bool]]:
    """Split content into alternating (text_block, is_table) segments.

    Contiguous lines matching ``|...|`` are grouped as a single table segment.
    Everything else is grouped as a text segment.

    Returns:
        List of ``(segment_text, is_table)`` tuples.
    """
    lines = content.split("\n")
    segments: list[tuple[str, bool]] = []
    current_lines: list[str] = []
    in_table = False

    for line in lines:
        is_table_line = bool(_TABLE_LINE_RE.match(line))

        if is_table_line != in_table:
            # Flush current segment
            if current_lines:
                text = "\n".join(current_lines)
                if text.strip():
                    segments.append((text, in_table))
                current_lines = []
            in_table = is_table_line

        current_lines.append(line)

    # Flush last segment
    if current_lines:
        text = "\n".join(current_lines)
        if text.strip():
            segments.append((text, in_table))

    return segments


def _split_section_content(
    content: str, chunk_size: int, overlap: int
) -> list[tuple[str, bool]]:
    """Split a single section's content into chunks, keeping tables intact.

    Returns:
        List of ``(chunk_text, has_table)`` tuples.
    """
    # If the whole section fits, return it directly
    if len(content) <= chunk_size:
        has_table = bool(_TABLE_LINE_RE.search(content))
        return [(content, has_table)]

    segments = _segment_text_and_tables(content)

    # If only one segment (no tables or all-table), use simpler logic
    if len(segments) == 1:
        seg_text, is_table = segments[0]
        if is_table:
            return [(t, True) for t in _split_table_by_rows(seg_text, chunk_size)]
        else:
            return [(t, False) for t in chunk_text(seg_text, chunk_size, overlap)]

    # Multiple segments: try to pack segments into chunks respecting chunk_size
    result: list[tuple[str, bool]] = []
    current_parts: list[str] = []
    current_len = 0
    current_has_table = False

    for seg_text, is_table in segments:
        seg_len = len(seg_text)

        if is_table and seg_len > chunk_size:
            # Flush accumulated text first
            if current_parts:
                result.append(("\n".join(current_parts), current_has_table))
                current_parts = []
                current_len = 0
                current_has_table = False
            # Split the oversized table
            for t in _split_table_by_rows(seg_text, chunk_size):
                result.append((t, True))
            continue

        if not is_table and seg_len > chunk_size:
            # Flush accumulated text first
            if current_parts:
                result.append(("\n".join(current_parts), current_has_table))
                current_parts = []
                current_len = 0
                current_has_table = False
            # Split the oversized text
            for t in chunk_text(seg_text, chunk_size, overlap):
                result.append((t, False))
            continue

        # Would adding this segment exceed chunk_size?
        added_len = seg_len + (1 if current_parts else 0)  # newline joiner
        if current_parts and current_len + added_len > chunk_size:
            result.append(("\n".join(current_parts), current_has_table))
            current_parts = []
            current_len = 0
            current_has_table = False

        current_parts.append(seg_text)
        current_len += added_len
        if is_table:
            current_has_table = True

    if current_parts:
        result.append(("\n".join(current_parts), current_has_table))

    return result


def _split_table_by_rows(table_text: str, chunk_size: int) -> list[str]:
    """Split an oversized Markdown table by rows, preserving the header.

    Keeps the first row (header) and the second row (separator ``|---|``)
    at the top of every chunk so that each chunk is a valid table fragment.
    """
    lines = table_text.split("\n")
    if len(lines) <= 2:
        return [table_text]

    # Identify header: first two lines (header + separator)
    header_lines = lines[:2]
    header_text = "\n".join(header_lines)
    header_len = len(header_text)

    data_lines = lines[2:]
    if not data_lines:
        return [table_text]

    chunks: list[str] = []
    current_rows: list[str] = []
    current_len = header_len

    for row in data_lines:
        row_len = len(row) + 1  # +1 for newline
        if current_rows and current_len + row_len > chunk_size:
            chunks.append(header_text + "\n" + "\n".join(current_rows))
            current_rows = []
            current_len = header_len

        current_rows.append(row)
        current_len += row_len

    if current_rows:
        chunks.append(header_text + "\n" + "\n".join(current_rows))

    return chunks if chunks else [table_text]
