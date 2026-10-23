"""Normalize resource URLs at the typed SQL boundary, within the source transaction.

Only typed conversation payload writes are interned. Reads expand references in SQL so
ORM and Core callers retain their existing string/JSON contracts. The catalog
is shared; authorization continues to belong to the enclosing business record.
"""

import datetime
import hashlib
import json
import re
import uuid
import sqlite3
from collections import OrderedDict

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

from ..entity.persistence.resource_url import ResourceURL


PREFIX = 'langbot-resource://'
REFERENCE = re.compile(r'langbot-resource://([a-f0-9-]{36})')
FIELDS = frozenset({'url', 'image_url', 'audio_url', 'file_url', 'video_url', 'original_url'})


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def digest(url):
    return hashlib.sha256(url.encode()).hexdigest()


def fields(value):
    if isinstance(value, list):
        for child in value:
            yield from fields(child)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in FIELDS and isinstance(child, str) and child.startswith(('http://', 'https://', '/api/v1/files/')):
                yield value, key, child
            else:
                yield from fields(child)


def intern(connection, raw, created_at=None, identities_out=None):
    """Intern resource fields synchronously in the current SQLAlchemy transaction."""
    if not isinstance(raw, str):
        return raw
    try:
        payload = json.loads(raw)
    except ValueError:
        return raw
    nodes = list(fields(payload))
    if not nodes:
        return raw
    table = ResourceURL.__table__
    stamp = now()
    urls = {url for _, _, url in nodes}
    aliases = connection.engine._langbot_resource_aliases
    known = {url: aliases[url] for url in urls if url in aliases}
    valid = (
        set(connection.execute(sa.select(table.c.id).where(table.c.id.in_(set(known.values())))).scalars())
        if known
        else set()
    )
    identities = {url: identity for url, identity in known.items() if identity in valid}
    urls -= identities.keys()
    hashes = dict(sorted((digest(url), url) for url in urls))
    insert = {'sqlite': sqlite.insert, 'postgresql': postgresql.insert}[connection.dialect.name]
    if hashes:
        connection.execute(
            insert(table)
            .values(
                [
                    dict(id=str(uuid.uuid4()), url=url, url_hash=key, created_at=created_at or stamp, updated_at=stamp)
                    for key, url in hashes.items()
                ]
            )
            .on_conflict_do_nothing(index_elements=['url_hash'])
        )
    for identity, url, key in connection.execute(
        sa.select(table.c.id, table.c.url, table.c.url_hash).where(table.c.url_hash.in_(hashes))
    ):
        if hashes[key] != url:
            raise ValueError('Resource URL hash collision')
        identities[url] = identity
    if created_at is not None and identities:
        # Migration order must not make an old shared URL appear newly created.
        connection.execute(
            table.update()
            .where(table.c.id.in_(set(identities.values())), table.c.created_at > created_at)
            .values(created_at=created_at)
        )
    for node, key, url in nodes:
        node[key] = PREFIX + identities[url]
        aliases[url] = identities[url]
        aliases.move_to_end(url)
    while len(aliases) > 8192:
        aliases.popitem(last=False)
    if identities_out is not None:
        identities_out.update(identities)
    return json.dumps(payload, ensure_ascii=False)


class ExpandedResourceURLs(FunctionElement):
    type = sa.Text()
    inherit_cache = True


class ExpandedResourceJSON(FunctionElement):
    type = sa.JSON()
    inherit_cache = True


@compiles(ExpandedResourceJSON)
def compile_json_expansion(element, compiler, **kw):
    expression = compile_expansion(element, compiler, **kw)
    if compiler.dialect.name == 'postgresql':
        return f'CAST({expression} AS JSON)'
    return expression


@compiles(ExpandedResourceURLs)
def compile_expansion(element, compiler, **kw):
    source = compiler.process(list(element.clauses)[0], **kw)
    if not getattr(compiler.dialect, '_langbot_resource_urls', False):
        return source
    return f'langbot_expand_resource_urls({source})'


def install(engine):
    """Enable normalization after schema initialization, before producers start."""
    engine.dialect._langbot_resource_urls = True
    if not hasattr(engine, '_langbot_resource_aliases'):
        engine._langbot_resource_aliases = OrderedDict()
    engine.clear_compiled_cache()
    if not sa.event.contains(engine, 'before_cursor_execute', normalize_parameters):
        sa.event.listen(engine, 'before_cursor_execute', normalize_parameters, retval=True)


def uninstall(engine):
    """Restore literal payload reads and writes after catalog downgrade."""
    if sa.event.contains(engine, 'before_cursor_execute', normalize_parameters):
        sa.event.remove(engine, 'before_cursor_execute', normalize_parameters)
    engine.dialect._langbot_resource_urls = False
    engine.clear_compiled_cache()
    engine._langbot_resource_aliases.clear()


def normalize_parameters(connection, cursor, statement, parameters, context, executemany):
    """Replace only typed payload binds; never inspect arbitrary SQL or configuration."""
    from .media import MediaReferenceText, MediaReferenceJSON

    compiled = context.compiled
    if compiled is None or not (context.isinsert or context.isupdate):
        return statement, parameters
    names = {
        name
        for bind, name in compiled.bind_names.items()
        if isinstance(bind.type, (MediaReferenceText, MediaReferenceJSON))
    }
    if not names:
        return statement, parameters

    def normalize(row):
        if isinstance(row, dict):
            return {key: intern(connection, value) if key in names else value for key, value in row.items()}
        positions = compiled.positiontup or []
        if not positions:
            return row
        return tuple(
            intern(connection, value) if positions[index % len(positions)] in names else value
            for index, value in enumerate(row)
        )

    batched = executemany and getattr(compiled, '_insertmanyvalues', None) is None
    return statement, [normalize(row) for row in parameters] if batched else normalize(parameters)


def register_sqlite(dbapi, record):
    """The UDF runs on aiosqlite's worker, including its catalog SELECTs."""
    driver = getattr(dbapi, 'driver_connection', None)
    raw_connection = driver._conn if hasattr(driver, '_conn') else dbapi
    if not isinstance(raw_connection, sqlite3.Connection):
        return

    def expand(raw):
        if not isinstance(raw, str) or PREFIX not in raw:
            return raw

        resolved = {}

        def lookup(match):
            identity = match.group(1)
            if identity in resolved:
                return resolved[identity]
            visited = set()
            while identity not in visited:
                visited.add(identity)
                row = raw_connection.execute(
                    'SELECT url, canonical_id FROM resource_urls WHERE id=?', (identity,)
                ).fetchone()
                if row is None:
                    raise ValueError('Missing resource URL')
                if row[1] is None:
                    value = json.dumps(row[0], ensure_ascii=False)[1:-1]
                    for reference in visited:
                        resolved[reference] = value
                    return value
                identity = row[1]
            raise ValueError('Cyclic resource URL reference')

        return REFERENCE.sub(lookup, raw)

    dbapi.create_function('langbot_expand_resource_urls', 1, expand)


POSTGRES_EXPANSION = r"""
CREATE OR REPLACE FUNCTION public.langbot_expand_resource_urls(payload text)
RETURNS text LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE token text; identity text; target text; parent text; result text := payload; visited text[];
BEGIN
  IF payload IS NULL OR position('langbot-resource://' in payload) = 0 THEN RETURN payload; END IF;
  FOR token IN SELECT DISTINCT m[1] FROM regexp_matches(payload, 'langbot-resource://([a-f0-9-]{36})', 'g') m LOOP
    identity := token; visited := ARRAY[]::text[];
    LOOP
      IF identity = ANY(visited) THEN RAISE EXCEPTION 'Cyclic resource URL reference'; END IF;
      visited := array_append(visited, identity);
      SELECT url, canonical_id INTO target, parent FROM resource_urls WHERE id = identity;
      IF NOT FOUND THEN RAISE EXCEPTION 'Missing resource URL'; END IF;
      EXIT WHEN parent IS NULL;
      identity := parent;
    END LOOP;
    result := replace(result, 'langbot-resource://' || token, substr(to_json(target)::text, 2, length(to_json(target)::text)-2));
  END LOOP;
  RETURN result;
END $$;
"""


def catalog_created(table, connection, **kw):
    if connection.dialect.name == 'postgresql':
        create_postgres_expansion(connection)
    install(connection.engine)


def create_postgres_expansion(connection):
    schema = connection.scalar(sa.select(sa.func.current_schema()))
    quoted = connection.dialect.identifier_preparer.quote(schema)
    connection.exec_driver_sql(POSTGRES_EXPANSION.replace('public', quoted))


async def refresh_images(engine, peer, payload, *, is_current=None):
    """Serialize refreshes on catalog identities and overwrite current URLs atomically."""
    from ..platform.adapters.aiocqhttp.image_urls import image_nodes

    nodes = list(image_nodes(payload))
    if not nodes:
        return

    def connected():
        return not peer.closed and (is_current is None or is_current())

    table = ResourceURL.__table__
    # Establish catalog identities for runtime-only inputs too. Existing history
    # already has identities created in its original write or migration.
    async with engine.begin() as db:
        references = {}
        await db.run_sync(lambda sync: intern(sync, json.dumps(payload), identities_out=references))
    identities = set(references.values())
    async with engine.connect() as db:
        if engine.dialect.name == 'sqlite':
            await db.exec_driver_sql('BEGIN IMMEDIATE')
        else:
            await db.begin()
        try:
            rows = (
                (
                    await db.execute(
                        sa.select(table).where(table.c.id.in_(identities)).order_by(table.c.id).with_for_update()
                    )
                )
                .mappings()
                .all()
            )
            by_id = {row['id']: row for row in rows}
            for identity in list(by_id):
                row = by_id[identity]
                while row['canonical_id'] is not None:
                    row = (
                        (await db.execute(sa.select(table).where(table.c.id == row['canonical_id']).with_for_update()))
                        .mappings()
                        .one()
                    )
                by_id[identity] = row
            by_url = {node['url']: by_id[references[node['url']]] for node, _, _ in nodes}
            # Capture origins even when renewal is not due or identification fails.
            for node, message_id, image_id in nodes:
                peer.image_urls.remember(by_url[node['url']]['url'], message_id, image_id)
            # Identification and upstream credential handling remain connection-local.
            if not connected() or not await peer.image_urls.identify():
                return
            napcat = peer.image_urls.app_name == 'NapCat.Onebot'
            due = []
            stamp = now()
            for node, message_id, image_id in nodes:
                row = by_url.get(node['url'])
                if row is None:
                    continue
                node['url'] = row['url']
                checked = row['last_checked_at'] or row['created_at']
                if napcat or (stamp - checked).total_seconds() >= 1800:
                    due.append((node, message_id, image_id, row))
            if due:
                # Keep Source/Image identities, including those recovered from events.
                batch = [
                    dict(message_id=message_id, image={'type': 'Image', 'image_id': image_id, 'url': node['url']})
                    for node, message_id, image_id, _ in due
                ]
                old = [entry['image']['url'] for entry in batch]
                completed = await peer.image_urls.refresh(batch)
                if not completed:
                    return
                if not connected():
                    return
                stamp = now()
                updated = set()
                for (node, _, _, row), entry, previous in zip(due, batch, old):
                    if previous not in completed:
                        continue
                    fresh = entry['image']['url']
                    node['url'] = fresh
                    if napcat and fresh == previous:
                        continue
                    if row['id'] in updated:
                        continue
                    updated.add(row['id'])
                    values = dict(last_checked_at=stamp)
                    if fresh != previous:
                        fresh_hash = digest(fresh)
                        # Lock the destination before merging identical current URLs.
                        destination = (
                            await db.execute(
                                sa.select(table.c.id, table.c.url)
                                .where(table.c.url_hash == fresh_hash)
                                .with_for_update()
                            )
                        ).first()
                        if destination is None:
                            try:
                                # Another source may discover the same renewed URL
                                # concurrently. Let the unique index arbitrate it.
                                async with db.begin_nested():
                                    await db.execute(
                                        table.update()
                                        .where(table.c.id == row['id'])
                                        .values(url=fresh, url_hash=fresh_hash, updated_at=stamp, **values)
                                    )
                                continue
                            except sa.exc.IntegrityError as exc:
                                if getattr(exc.orig, 'sqlstate', None) != '23505':
                                    raise
                                destination = (
                                    await db.execute(
                                        sa.select(table.c.id, table.c.url)
                                        .where(table.c.url_hash == fresh_hash)
                                        .with_for_update()
                                    )
                                ).one()
                        if destination is not None and destination.id != row['id']:
                            if destination.url != fresh:
                                raise ValueError('Resource URL hash collision')
                            values.update(url=None, url_hash=None, canonical_id=destination.id, updated_at=stamp)
                            await db.execute(
                                table.update().where(table.c.id == destination.id).values(last_checked_at=stamp)
                            )
                        else:
                            values.update(url=fresh, url_hash=fresh_hash, updated_at=stamp)
                    await db.execute(table.update().where(table.c.id == row['id']).values(**values))
            await db.commit()
        except BaseException:
            await db.rollback()
            raise


sa.event.listen(sa.engine.Engine, 'connect', register_sqlite)
sa.event.listen(ResourceURL.__table__, 'after_create', catalog_created)
