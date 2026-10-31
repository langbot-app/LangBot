"""Datetime values bound to LangBot's timezone-less SQL columns."""

from __future__ import annotations

import datetime


def as_naive_utc(value: datetime.datetime | None) -> datetime.datetime | None:
    """Keep the existing UTC-naive storage contract on SQLite and PostgreSQL.

    Legacy naive values already represent UTC. Aware values must be converted
    to UTC *before* dropping tzinfo, including query cutoffs and deadlines.
    This is a bind-boundary conversion, not a schema or wire-format change.
    """
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
