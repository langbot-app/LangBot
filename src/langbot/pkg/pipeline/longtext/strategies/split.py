from __future__ import annotations

import re

from .. import strategy as strategy_model

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message


@strategy_model.strategy_class('split')
class SplitStrategy(strategy_model.LongTextStrategy):
    """Split long text into multiple message segments with Markdown awareness."""

    async def process(self, message: str, query: pipeline_query.Query) -> list[platform_message.MessageComponent]:
        segments = self.split_text(
            message,
            query.pipeline_config['output']['long-text-processing']['threshold'],
        )
        return [platform_message.Plain(text=segments[0])] if segments else []

    def split_text(self, text: str, max_length: int) -> list[str]:
        """Split text into segments respecting Markdown structure.

        Priority:
            1. Markdown structural boundaries (headings, code blocks, horizontal rules)
            2. Paragraph breaks (blank lines)
            3. List item boundaries
            4. Line breaks
            5. Hard cut (fallback)
        """
        if len(text) <= max_length:
            return [text]

        blocks = self._parse_markdown_blocks(text)
        return self._merge_blocks(blocks, max_length)

    def _parse_markdown_blocks(self, text: str) -> list[str]:
        """Parse text into Markdown-aware blocks.

        Keeps code blocks intact and splits the rest by structural elements.
        """
        blocks: list[str] = []
        lines = text.split('\n')
        current_block: list[str] = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()

            # Toggle fenced code block state
            if stripped.startswith('```'):
                if in_code_block:
                    # End of code block - close it as one block
                    current_block.append(line)
                    blocks.append('\n'.join(current_block))
                    current_block = []
                    in_code_block = False
                    continue
                else:
                    # Start of code block - flush current block first
                    if current_block:
                        blocks.append('\n'.join(current_block))
                        current_block = []
                    current_block.append(line)
                    in_code_block = True
                    continue

            if in_code_block:
                current_block.append(line)
                continue

            # Heading (# ...) - start a new block
            if re.match(r'^#{1,6}\s', stripped):
                if current_block:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                current_block.append(line)
                continue

            # Horizontal rule (---, ***, ___) - start a new block
            if re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', stripped):
                if current_block:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                blocks.append(line)
                continue

            # Blank line - paragraph boundary
            if stripped == '':
                if current_block:
                    current_block.append(line)
                    blocks.append('\n'.join(current_block))
                    current_block = []
                continue

            current_block.append(line)

        # Flush remaining (including unclosed code blocks)
        if current_block:
            blocks.append('\n'.join(current_block))

        return [b for b in blocks if b.strip()]

    def _merge_blocks(self, blocks: list[str], max_length: int) -> list[str]:
        """Merge small blocks greedily until approaching max_length.

        If a single block exceeds max_length, split it by lines as fallback.
        """
        segments: list[str] = []
        current = ''

        for block in blocks:
            candidate = (current + '\n\n' + block) if current else block

            if len(candidate) <= max_length:
                current = candidate
            else:
                # Flush current segment
                if current:
                    segments.append(current)

                # Check if this single block fits
                if len(block) <= max_length:
                    current = block
                else:
                    # Block too large - split it by lines
                    for part in self._split_large_block(block, max_length):
                        segments.append(part)
                    current = ''

        if current:
            segments.append(current)

        return [s for s in segments if s.strip()]

    def _split_large_block(self, block: str, max_length: int) -> list[str]:
        """Split an oversized block by lines, preserving code block fences.

        For single-line plain text (no newlines), falls back to splitting at
        natural language boundaries (spaces, punctuation).
        """
        lines = block.split('\n')

        # Single long line with no newlines - use plain text splitting
        if len(lines) == 1:
            return self._split_plain_text(block, max_length)

        is_code_block = lines[0].strip().startswith('```')

        segments: list[str] = []
        current_lines: list[str] = []
        current_len = 0

        # For code blocks, track the opening fence to re-apply on continuations
        code_fence = lines[0] if is_code_block else ''

        for i, line in enumerate(lines):
            line_len = len(line) + 1  # +1 for newline

            # Single line exceeds limit on its own - split it first
            if line_len > max_length:
                if current_lines:
                    seg = '\n'.join(current_lines)
                    if is_code_block and not seg.rstrip().endswith('```'):
                        seg += '\n```'
                    segments.append(seg)
                    current_lines = []
                    current_len = 0

                for part in self._split_plain_text(line, max_length):
                    segments.append(part)
                continue

            if current_len + line_len > max_length and current_lines:
                segment = '\n'.join(current_lines)
                # Close code block fence if splitting mid-code-block
                if is_code_block and not segment.rstrip().endswith('```'):
                    segment += '\n```'
                segments.append(segment)

                current_lines = []
                current_len = 0
                # Re-open code block fence for continuation
                if is_code_block and i < len(lines) - 1 and not line.strip().startswith('```'):
                    current_lines.append(code_fence)
                    current_len = len(code_fence) + 1

            current_lines.append(line)
            current_len += line_len

        if current_lines:
            segments.append('\n'.join(current_lines))

        return segments

    def _split_plain_text(self, text: str, max_length: int) -> list[str]:
        """Split a long plain text string (no newlines) at word/space boundaries."""
        if len(text) <= max_length:
            return [text]

        segments: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                segments.append(remaining)
                break

            chunk = remaining[:max_length]
            min_pos = int(max_length * 0.3)

            # Try to find a space to split at
            pos = chunk.rfind(' ')
            if pos >= min_pos:
                split_pos = pos
            else:
                # Hard cut as last resort
                split_pos = max_length

            segments.append(remaining[:split_pos].rstrip())
            remaining = remaining[split_pos:].lstrip()

        return [s for s in segments if s]
