from __future__ import annotations

import abc

from langbot_plugin.api.definition.components.base import BaseComponent
from langbot_plugin.api.entities.builtin.rag.models import (
    ParseContext,
    ParseResult,
)


class Parser(BaseComponent):
    """Parser component that extracts structured text from binary files.

    This component is invoked before KnowledgeEngine.ingest() to parse files like
    PDF, Word, Markdown, etc. into structured text.

    A single parser can declare support for multiple MIME types via the
    manifest's `supported_mime_types` field.
    """

    __kind__ = "Parser"

    @abc.abstractmethod
    async def parse(self, context: ParseContext) -> ParseResult:
        """Parse a file and extract structured text.

        Args:
            context: Parse context containing raw file bytes, MIME type,
                     filename, and metadata.

        Returns:
            ParseResult with extracted text and optional structured sections.
        """
        pass
