"""Bounded, backend-independent selection of complete memory records."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any

MAX_RECALL_CHARS = 8000
MAX_PROFILE_CHARS = 2000
MAX_RECALL_RESULTS = 20


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def currently_valid(metadata: dict, now: datetime) -> bool:
    start = parse_time(metadata.get("valid_from"))
    end = parse_time(metadata.get("valid_until"))
    if (metadata.get("valid_from") and start is None) or (
        metadata.get("valid_until") and end is None
    ):
        return False
    return (start is None or start <= now) and (end is None or now < end)


def matches_filters(metadata: dict, filters: dict | None) -> bool:
    """Recheck Host-controlled filters for ID lookups and backend responses."""
    if not filters:
        return True
    if "$and" in filters:
        return all(matches_filters(metadata, item) for item in filters["$and"])
    for key, expected in filters.items():
        actual = str(metadata.get(key, ""))
        if isinstance(expected, dict):
            if not actual or any(
                (operator == "$gte" and actual < str(value))
                or (operator == "$lte" and actual > str(value))
                or operator not in {"$gte", "$lte"}
                for operator, value in expected.items()
            ):
                return False
        elif actual != str(expected):
            return False
    return True


def exact_match_score(query: str, item_id: str, metadata: dict) -> float:
    needle = query.strip().casefold()
    if not needle:
        return 0.0
    score = 2.0 if needle == str(item_id).casefold() else 0.0
    for field in ("sender_id", "sender_name"):
        if needle == str(metadata.get(field, "")).strip().casefold():
            score += 1.2
    if needle in {
        tag.strip().casefold() for tag in str(metadata.get("tags", "")).split(",")
    }:
        score += 1.2
    if needle in str(metadata.get("content", "")).casefold():
        score += 0.6
    return score


def _terms(content: str) -> set[str]:
    content = content.casefold()
    words = set(re.findall(r"\w+", content.casefold()))
    # Character shingles also work for CJK text without a tokenizer dependency.
    words.update(
        content[index : index + 3] for index in range(max(0, len(content) - 2))
    )
    return words


def _source_ids(metadata: dict) -> set[str]:
    try:
        sources = json.loads(metadata.get("consolidation_source_ids", "[]"))
    except (ValueError, TypeError):
        return set()
    return (
        {item for item in sources if isinstance(item, str)}
        if isinstance(sources, list)
        else set()
    )


def select_memories(
    records: list[dict],
    query: str,
    *,
    top_k: int = 5,
    exact_match_boost: bool = True,
    current_sender_id: str = "",
    historical: bool = False,
    max_chars: int = MAX_RECALL_CHARS,
    half_life_days: float = 30.0,
    now: datetime | None = None,
) -> list[dict]:
    """Use backend rank as relevance; scores/distances have no shared calibration.

    Complete serialized records count against the character budget. Oversized
    records are omitted instead of truncating facts or producing partial JSON.
    """
    now = now or datetime.now(timezone.utc)
    try:
        half_life_days = float(half_life_days)
        if not math.isfinite(half_life_days) or half_life_days <= 0:
            half_life_days = 30.0
    except (ValueError, TypeError):
        half_life_days = 30.0
    candidates = []
    identities = set()
    for rank, record in enumerate(records):
        metadata = record.get("metadata", {})
        if not historical and not currently_valid(metadata, now):
            continue
        content = str(metadata.get("content", "") or "")
        if not content or len(content) > max_chars:
            continue
        if len(json.dumps(record, ensure_ascii=False, default=str)) + 2 > max_chars:
            continue
        identity = (
            " ".join(content.casefold().split()),
            str(metadata.get("sender_id", "")),
            str(metadata.get("event_at") or metadata.get("timestamp", "")),
            str(metadata.get("valid_from", "")),
            str(metadata.get("valid_until", "")),
        )
        if identity in identities:
            continue
        identities.add(identity)
        try:
            importance = min(5, max(1, int(metadata.get("importance", 2))))
        except (ValueError, TypeError):
            importance = 2
        score = 0.1 / (rank + 1) + (importance - 2) * 0.0025
        event_at = parse_time(metadata.get("event_at"))
        if event_at is not None:
            age = max(0.0, (now - event_at).total_seconds() / 86400)
            score += 0.008 * math.exp(-math.log(2) * age / half_life_days)
        if (
            current_sender_id
            and str(metadata.get("sender_id", "")) == current_sender_id
        ):
            score += 0.004
        if exact_match_boost:
            score += exact_match_score(query, str(record.get("id", "")), metadata)
        candidates.append((record, score, _terms(content)))
    chosen = []
    chosen_terms: list[set[str]] = []
    covered_ids: set[str] = set()
    used_chars = 2
    while candidates and len(chosen) < max(0, min(MAX_RECALL_RESULTS, top_k)):

        def diverse_score(candidate):
            terms = candidate[2]
            overlap = max(
                (
                    len(terms & prior) / max(1, len(terms | prior))
                    for prior in chosen_terms
                ),
                default=0.0,
            )
            return candidate[1] - overlap * 0.015

        best = max(
            range(len(candidates)), key=lambda index: diverse_score(candidates[index])
        )
        record, _score, terms = candidates.pop(best)
        ids = {str(record.get("id", ""))} | _source_ids(record.get("metadata", {}))
        if ids & covered_ids:
            continue
        size = len(json.dumps(record, ensure_ascii=False, default=str)) + 2
        if used_chars + size > max_chars:
            continue
        chosen.append(record)
        chosen_terms.append(terms)
        covered_ids.update(ids)
        used_chars += size
    return chosen


def bounded_profile(text: str) -> str:
    return (
        text if len(json.dumps(text, ensure_ascii=False)) <= MAX_PROFILE_CHARS else ""
    )
