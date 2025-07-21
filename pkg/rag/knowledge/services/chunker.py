from __future__ import annotations

import json
from typing import List
from pkg.rag.knowledge.services import base_service
from pkg.core import app


class Chunker(base_service.BaseService):
    """
    A class for splitting long texts into smaller, overlapping chunks.
    """

    def __init__(self, ap: app.Application, chunk_size: int = 500, chunk_overlap: int = 50):
        self.ap = ap
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        if self.chunk_overlap >= self.chunk_size:
            self.ap.logger.warning(
                'Chunk overlap is greater than or equal to chunk size. This may lead to empty or malformed chunks.'
            )

    def _split_text_sync(self, text: str) -> List[str]:
        """
        Synchronously splits a long text into chunks with specified overlap.
        This is a CPU-bound operation, intended to be run in a separate thread.
        """
        if not text:
            return []
        # words = text.split()
        # chunks = []
        # current_chunk = []

        # for word in words:
        #     current_chunk.append(word)
        #     if len(current_chunk) > self.chunk_size:
        #         chunks.append(" ".join(current_chunk[:self.chunk_size]))
        #         current_chunk = current_chunk[self.chunk_size - self.chunk_overlap:]

        # if current_chunk:
        #     chunks.append(" ".join(current_chunk))

        # A more robust chunking strategy (e.g., using recursive character text splitter)
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        return text_splitter.split_text(text)

    async def chunk(self, text: str) -> List[str]:
        """
        Asynchronously chunks a given text into smaller pieces.
        """
        self.ap.logger.info(f'Chunking text (length: {len(text)})...')
        # Run the synchronous splitting logic in a separate thread
        chunks = await self._run_sync(self._split_text_sync, text)
        self.ap.logger.info(f'Text chunked into {len(chunks)} pieces.')
        self.ap.logger.debug(f'Chunks: {json.dumps(chunks, indent=4, ensure_ascii=False)}')
        return chunks
