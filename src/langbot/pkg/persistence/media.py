"""The storage contract for conversation payloads containing image references."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.operators import OperatorType
from sqlalchemy.types import TypeDecorator


class MediaReferenceText(TypeDecorator[str]):
    """Keep the existing TEXT format while rejecting structured inline images.

    Writers must externalize retained images through MediaCache or redact
    metadata-only images before binding a value. Both ORM and Core writes use
    this contract; reads preserve historical values for incremental cleanup.
    Plain text remains valid for fields such as monitoring message content.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return value

        # Model imports must not initialize the media cache's runtime dependencies.
        from ..storage.media import MediaCache

        if MediaCache.has_inline_images(payload):
            raise ValueError(
                'Inline images cannot be persisted; use MediaCache.externalize_chain_dump() '
                'for retained content or MediaCache.redact_inline_images() for metadata'
            )
        return value

    def coerce_compared_value(self, op: OperatorType | None, value: Any) -> Text:
        # Legacy payloads must remain usable in searches and compare-and-swap updates.
        return self.impl
