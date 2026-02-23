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
) -> list[tuple[str, str, Any]]:
    """Return only triples whose field is in *supported_fields*.

    Dropped fields are logged at WARNING level so the caller knows they were
    silently ignored (useful for Milvus / pgvector which only store a fixed
    schema).
    """
    kept: list[tuple[str, str, Any]] = []
    for field, op, value in triples:
        if field in supported_fields:
            kept.append((field, op, value))
        else:
            logger.warning(
                'Filter field %r is not supported by this backend and will be ignored '
                '(supported: %s)',
                field,
                ', '.join(sorted(supported_fields)),
            )
    return kept
