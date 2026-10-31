"""Safe PostgreSQL URL normalization shared by runtime and migration jobs."""

from __future__ import annotations

import sqlalchemy


def normalize_asyncpg_url(url: sqlalchemy.engine.URL) -> sqlalchemy.engine.URL:
    """Select asyncpg and translate the common libpq TLS query spelling."""

    if url.drivername == 'postgresql':
        url = url.set(drivername='postgresql+asyncpg')
    elif url.drivername != 'postgresql+asyncpg':
        raise ValueError('PostgreSQL URL must use PostgreSQL with the asyncpg driver')

    query = dict(url.query)
    sslmode = query.pop('sslmode', None)
    if sslmode is not None:
        if 'ssl' in query and query['ssl'] != sslmode:
            raise ValueError('PostgreSQL URL cannot specify conflicting ssl and sslmode options')
        # SQLAlchemy expands URL query keys into asyncpg keyword arguments.
        # asyncpg calls this keyword ``ssl`` even though PostgreSQL DSNs
        # conventionally spell the same mode ``sslmode``.
        query['ssl'] = sslmode
    return url.set(query=query)
