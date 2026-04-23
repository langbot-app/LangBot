"""Shared utilities for metadata filter handling across VDB backends.

Canonical filter format (Chroma-style ``where`` syntax):

    {"file_id": "abc"}                      # implicit $eq
    {"file_id": {"$eq": "abc"}}             # explicit $eq
    {"created_at": {"$gte": 1700000000}}    # comparison
    {"file_type": {"$in": ["pdf", "docx"]}} # in-list

Multiple top-level keys are AND-ed.  Supported operators:
``$eq``, ``$ne``, ``$gt``, ``$gte``, ``$lt``, ``$lte``, ``$in``, ``$nin``.
"""

from __future__ import annotations

import logging
from typing import Any

SUPPORTED_OPS = frozenset({'$eq', '$ne', '$gt', '$gte', '$lt', '$lte', '$in', '$nin'})

logger = logging.getLogger(__name__)


def normalize_filter(
    raw: dict[str, Any] | None,
) -> list[tuple[str, str, Any]]:
    """Parse a canonical filter dict into ``[(field, op, value)]`` triples.

    Returns an empty list when *raw* is ``None`` or empty.

    Raises ``ValueError`` on unsupported operators or malformed entries.
    """
    if not raw:
        return []

    triples: list[tuple[str, str, Any]] = []
    for field, condition in raw.items():
        if isinstance(condition, dict):
            for op, value in condition.items():
                if op not in SUPPORTED_OPS:
                    raise ValueError(f'Unsupported filter operator: {op}')
                triples.append((field, op, value))
        else:
            # Bare value -> implicit $eq
            triples.append((field, '$eq', condition))
    return triples


def strip_unsupported_fields(
    triples: list[tuple[str, str, Any]],
    supported_fields: set[str],
    field_aliases: dict[str, str] | None = None,
) -> list[tuple[str, str, Any]]:
    """Return only triples whose field is in *supported_fields*.

    If *field_aliases* is provided, aliased field names are mapped to the
    canonical backend name before the support check.  For example,
    ``{'uuid': 'chunk_uuid'}`` allows callers to use ``uuid`` which is
    transparently rewritten to ``chunk_uuid``.

    Dropped fields are logged at WARNING level so the caller knows they were
    silently ignored (useful for Milvus / pgvector which only store a fixed
    schema).
    """
    aliases = field_aliases or {}
    kept: list[tuple[str, str, Any]] = []
    for field, op, value in triples:
        resolved = aliases.get(field, field)
        if resolved in supported_fields:
            kept.append((resolved, op, value))
        else:
            logger.warning(
                'Filter field %r is not supported by this backend and will be ignored (supported: %s)',
                field,
                ', '.join(sorted(supported_fields)),
            )
    return kept
