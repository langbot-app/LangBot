"""The storage contract for conversation payloads containing image references."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text, JSON, cast
from sqlalchemy.sql.elements import ColumnElement
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

    class comparator_factory(Text.Comparator):
        def operate(self, op, *other, **kw):
            from .resource_urls import ExpandedResourceURLs

            # ORM identity maps compare annotated copies of mapped columns.
            if other and isinstance(other[0], ColumnElement) and self.expr.shares_lineage(other[0]):
                return super().operate(op, *other, **kw)
            # CAS and textual filters compare the same expanded value readers see.
            return op(ExpandedResourceURLs(self.expr), *other, **kw)

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        reject_internal_references(value)
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

    def column_expression(self, column):
        from .resource_urls import ExpandedResourceURLs

        return ExpandedResourceURLs(column)


class MediaReferenceJSON(TypeDecorator):
    """Preserve native JSON API values while interning structured resource fields."""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            reject_internal_references(json.dumps(value))
        return value

    def column_expression(self, column):
        from .resource_urls import ExpandedResourceJSON

        return ExpandedResourceJSON(cast(column, Text))


def reject_internal_references(value):
    """Only the transactional normalizer may introduce catalog references."""
    from .resource_urls import REFERENCE

    if REFERENCE.search(value):
        raise ValueError('Internal resource references cannot be supplied as conversation content')


# Register the catalog and its database hooks before engines are opened.
from . import resource_urls as _resource_urls  # noqa: E402,F401
