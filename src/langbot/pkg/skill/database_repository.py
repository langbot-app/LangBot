from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import tempfile
import uuid
from collections import OrderedDict
from functools import partial

import sqlalchemy
from langbot_plugin.skill_store import SkillRevisionConflictError, SkillRevisionNotFoundError, SkillStore
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..entity.persistence.skill import SkillRegistry, SkillVersion
from ..utils.bounded_executor import BlockingWorkCapacityError, run_blocking_atomic


MAX_PUBLICATION_BYTES = 64 * 1024 * 1024
_RESOURCE_CACHE_BYTES = 32 * 1024 * 1024
_RESOURCE_CACHE_ENTRIES = 256
_LOCAL_FIELDS = {'package_root', 'manifest_path', 'source_path'}


class DatabaseSkillRepository:
    """Use the database as authority and the SDK store only for disposable trees."""

    def __init__(self, ap, cache: SkillStore, validate_context):
        self.ap = ap
        self.cache = cache
        self._validate_context = validate_context
        self._resource_archives = OrderedDict()
        self._resource_archive_bytes = 0

    @property
    def content(self):
        return self.ap.storage_mgr.content_store

    def _discard_resource_archive(self, key):
        cached = self._resource_archives.pop(key, None)
        if cached is not None:
            self._resource_archive_bytes -= len(cached['value'])

    def _remember_resource_archive(self, key, archive, metadata):
        self._discard_resource_archive(key)
        if len(archive) > _RESOURCE_CACHE_BYTES:
            return
        while self._resource_archives and (
            self._resource_archive_bytes + len(archive) > _RESOURCE_CACHE_BYTES
            or len(self._resource_archives) >= _RESOURCE_CACHE_ENTRIES
        ):
            self._discard_resource_archive(next(iter(self._resource_archives)))
        self._resource_archives[key] = {'value': archive, 'size': metadata['size'], 'digest': metadata['digest']}
        self._resource_archive_bytes += len(archive)

    @staticmethod
    async def _read_resource_parallel(validate_digest, read_resource):
        async def verify():
            digest, result = await asyncio.gather(
                run_blocking_atomic(validate_digest),
                run_blocking_atomic(read_resource),
                return_exceptions=True,
            )
            if isinstance(digest, BlockingWorkCapacityError):
                digest = await run_blocking_atomic(validate_digest)
            if isinstance(digest, BaseException):
                raise digest
            if isinstance(result, BlockingWorkCapacityError):
                result = await run_blocking_atomic(read_resource)
            if isinstance(result, BaseException):
                raise result
            return result

        driver = asyncio.create_task(verify())
        try:
            return await asyncio.shield(driver)
        except asyncio.CancelledError:
            # Keep the Workspace lock until every admitted check actually finishes.
            drained = asyncio.gather(driver, return_exceptions=True)
            while not drained.done():
                try:
                    await asyncio.shield(drained)
                except asyncio.CancelledError:
                    continue
            raise

    async def _resource_archive_row(self, uow, context, content_ref):
        """Check live authority before considering a disposable archive cache hit."""
        cache_key = (context.instance_uuid, context.workspace_uuid, content_ref)
        cached = self._resource_archives.get(cache_key)
        row = await self.content._row(uow, context.workspace_uuid, content_ref, metadata_only=cached is not None)
        if cached is not None and (cached['size'], cached['digest']) != (row['size'], row['digest']):
            self._discard_resource_archive(cache_key)
            cached = None
            row = await self.content._row(uow, context.workspace_uuid, content_ref)
        return cache_key, cached, row

    async def _read_resource_archive(self, cache_key, cached, row, reader, *args, **kwargs):
        """Share bounded verified package bytes, never authorization or extracted files.

        Callers hold the repository Workspace lock and have released the database
        connection before entering this helper. A cache hit still verifies the live
        digest and full archive manifest on the bounded worker scope.
        """
        content = self.content
        try:
            archive = cached['value'] if cached is not None else bytes(await content._read(row, MAX_PUBLICATION_BYTES))
            read_resource = partial(reader, archive, *args, **kwargs)
            scope_limit = getattr(getattr(self.ap, 'blocking_executor', None), 'max_inflight_per_scope', 0)
            if cached is not None and isinstance(scope_limit, int) and scope_limit >= 2:
                result = await self._read_resource_parallel(
                    partial(content._validated_value, archive, row, MAX_PUBLICATION_BYTES), read_resource
                )
            else:
                if cached is not None:
                    content._validated_value(archive, row, MAX_PUBLICATION_BYTES)
                result = await run_blocking_atomic(read_resource)
        except BaseException:
            self._discard_resource_archive(cache_key)
            raise
        self._remember_resource_archive(cache_key, archive, row)
        return result

    @staticmethod
    def _scope(model, context):
        return (
            model.workspace_uuid == context.workspace_uuid,
            model.instance_uuid == context.instance_uuid,
        )

    async def _record(self, context, name: str, revision: str | None = None) -> dict | None:
        name = SkillStore._validate_skill_name(name)
        if revision is not None:
            SkillStore._validate_revision(revision)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            registry = None
            if revision is None:
                registry = (
                    await uow.execute(
                        sqlalchemy.select(SkillRegistry).where(
                            *self._scope(SkillRegistry, context), SkillRegistry.name == name
                        )
                    )
                ).scalar_one_or_none()
                if registry is None:
                    return None
                revision = registry.current_revision
            version = (
                await uow.execute(
                    sqlalchemy.select(SkillVersion).where(
                        *self._scope(SkillVersion, context),
                        SkillVersion.name == name,
                        SkillVersion.revision == revision,
                    )
                )
            ).scalar_one_or_none()
            if version is None:
                raise SkillRevisionNotFoundError(f'Skill "{name}" pinned revision {revision} is unavailable')
            return {
                'skill': dict(registry.skill_json if registry is not None else version.skill_json),
                'manifest': version.manifest_json,
                'content_ref': version.content_ref,
                'version_id': version.uuid,
            }

    @staticmethod
    def _artifact_resource_metadata(record, path):
        """Describe a manifest member, never an object-store key supplied by a caller."""
        path = SkillStore._publication_resource_path(path)
        _, revision, manifest = SkillStore._publication_manifest_identity(record['skill'], record['manifest'])
        entry = next((item for item in manifest['files'] if item['path'] == path), None)
        if entry is None:
            raise FileNotFoundError('Skill resource not found')
        # Match the existing SDK's verified publication reader ceiling.
        if entry['size'] > 1024 * 1024:
            raise ValueError('Skill resource exceeds the 1048576-byte limit')
        return {
            'version_id': record['version_id'],
            'content_ref': record['content_ref'],
            'revision': revision,
            'path': path,
            'digest': entry['sha256'],
            'size': entry['size'],
            'mime_type': mimetypes.guess_type(path)[0] or 'application/octet-stream',
            'name': record['skill']['name'],
        }

    async def resolve_artifact_resource(self, context, name, path, *, expected_revision, max_bytes=1024 * 1024):
        """Resolve an explicitly pinned publication; authorization belongs to the caller."""
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError('Skill resource read limit must be a positive integer')
        if not expected_revision:
            raise ValueError('Skill Artifact resources require an explicit revision')
        await self._validate_context(context)
        record = await self._record(context, name, expected_revision)
        if record is None:
            raise FileNotFoundError('Skill resource not found')
        source = self._artifact_resource_metadata(record, path)
        # Enforce the caller's remaining budget before fetching or verifying archive bytes.
        if source['size'] > max_bytes:
            raise ValueError('Skill resource exceeds the requested read limit')
        # Do not return a successful reference to a corrupt or unavailable package.
        await self.read_artifact_resource(context, source, max_bytes=max_bytes)
        return source

    async def read_artifact_resource(self, context, source, *, max_bytes):
        """Read a version UUID, independent of registry names, aliases and local caches."""
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError('Skill resource read limit must be a positive integer')
        await self._validate_context(context)
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            version = (
                await uow.execute(
                    sqlalchemy.select(SkillVersion).where(
                        *self._scope(SkillVersion, context), SkillVersion.uuid == source.get('version_id')
                    )
                )
            ).scalar_one_or_none()
            if version is None:
                raise FileNotFoundError('Skill resource not found')
            record = {
                'version_id': version.uuid,
                'content_ref': version.content_ref,
                'skill': dict(version.skill_json),
                'manifest': version.manifest_json,
            }
            expected = self._artifact_resource_metadata(record, source.get('path'))
            # MIME is persisted presentation metadata, not immutable byte identity.
            # Replacement hosts may have different system MIME registries.
            for key in ('content_ref', 'revision', 'path', 'digest', 'size'):
                if source.get(key) != expected[key]:
                    raise ValueError('Skill resource identity does not match its publication')
            if expected['size'] > max_bytes:
                raise ValueError('Skill resource exceeds the requested read limit')
            await self.content._validate(context)
            cache_key, cached, row = await self._resource_archive_row(uow, context, record['content_ref'])
        # The Artifact read lease protects this package during object-store IO.
        _, _, value = await self._read_resource_archive(
            cache_key,
            cached,
            row,
            partial(SkillStore._publication_resource, record['skill'], record['manifest']),
            expected['path'],
            expected['revision'],
        )
        if value is None or len(value) != expected['size'] or hashlib.sha256(value).hexdigest() != expected['digest']:
            raise ValueError('Skill resource content does not match its publication')
        return value

    async def _archive(self, context, record: dict) -> bytes:
        return await self.content.get(context, record['content_ref'], max_bytes=MAX_PUBLICATION_BYTES)

    async def _materialize(self, context, namespace: str, record: dict, archive: bytes | None = None) -> dict:
        store = self.cache.scoped(namespace)
        skill = record['skill']

        def cached():
            try:
                result = store.get_skill_snapshot(skill['name'], skill['revision'])
            except SkillRevisionNotFoundError:
                return None
            if result is not None:
                result.update(skill)
            return result

        result = await run_blocking_atomic(cached)
        if result is not None:
            return result
        archive = archive if archive is not None else await self._archive(context, record)
        result = await run_blocking_atomic(store.restore_skill_publication, skill, record['manifest'], archive)
        result.update(skill)
        return result

    async def get_package(
        self, context, name: str, revision: str | None = None, *, metadata_only: bool = False
    ) -> dict:
        if metadata_only:
            async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid):
                record = await self._record(context, name, revision)
                if record is None:
                    raise ValueError(f'Skill "{name}" not found')
                metadata = await self.content.metadata(context, record['content_ref'])
            return {
                'revision': record['skill']['revision'],
                'manifest': record['manifest'],
                'filename': f'{record["skill"]["name"]}.zip',
                'sha256': metadata['digest'],
                'size': metadata['size'],
            }
        record = await self._record(context, name, revision)
        if record is None:
            raise ValueError(f'Skill "{name}" not found')
        package = {
            'revision': record['skill']['revision'],
            'manifest': record['manifest'],
            'filename': f'{record["skill"]["name"]}.zip',
        }
        content = await self._archive(context, record)
        package.update(content=content, sha256=hashlib.sha256(content).hexdigest(), size=len(content))
        return package

    async def _import_zip(self, context, file_bytes: bytes, data: dict, *, base_revision: str | None) -> dict:
        with tempfile.TemporaryDirectory(prefix='langbot-skill-draft-') as temporary:
            store = SkillStore(temporary + '/store')
            source, payload = await run_blocking_atomic(store._prepare_skill_zip, file_bytes, temporary, data)
            current = await self._record(context, payload['name'])
            if current is not None:
                SkillStore._require_base_revision(
                    payload['name'], {'current_revision': current['skill']['revision']}, base_revision
                )

            def publish():
                result = store.import_skill_directory(
                    source, payload, source_root=temporary, base_revision=base_revision if current is None else None
                )
                publication = store.export_skill_publication(result['name'])
                if current is not None and 'created_at' in current['skill']:
                    publication['skill']['created_at'] = current['skill']['created_at']
                return publication

            publication = await run_blocking_atomic(publish)
        await self._publish(
            context,
            [publication],
            {payload['name']: current['skill']['revision'] if current is not None else None},
        )
        return dict(publication['skill'])

    async def _publish(self, context, publications: list[dict], bases: dict[str, str | None]) -> None:
        for publication in publications:
            if len(publication['file_bytes']) > MAX_PUBLICATION_BYTES:
                raise ValueError('Skill publication archive exceeds the 64 MiB database persistence limit')
        async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            dialect = self.ap.persistence_mgr.get_db_engine().dialect.name
            if dialect not in {'sqlite', 'postgresql'}:
                raise ValueError('Persistent Skills require PostgreSQL or SQLite')
            insert = sqlite_insert if dialect == 'sqlite' else pg_insert
            for publication in publications:
                skill = json.loads(
                    json.dumps(
                        {key: value for key, value in publication['skill'].items() if key not in _LOCAL_FIELDS},
                        ensure_ascii=False,
                        default=str,
                    )
                )
                publication['skill'] = skill
                name, revision = skill['name'], skill['revision']
                values = {
                    'workspace_uuid': context.workspace_uuid,
                    'instance_uuid': context.instance_uuid,
                    'name': name,
                    'current_revision': revision,
                    'skill_json': skill,
                }
                base = bases[name]
                if base is None:
                    statement = (
                        insert(SkillRegistry)
                        .values(uuid=str(uuid.uuid4()), **values)
                        .on_conflict_do_nothing(index_elements=['workspace_uuid', 'instance_uuid', 'name'])
                    )
                else:
                    statement = (
                        sqlalchemy.update(SkillRegistry)
                        .where(
                            *self._scope(SkillRegistry, context),
                            SkillRegistry.name == name,
                            SkillRegistry.current_revision == base,
                        )
                        .values(current_revision=revision, skill_json=skill)
                    )
                if (await uow.execute(statement)).rowcount != 1:
                    raise SkillRevisionConflictError(f'Skill "{name}" changed since the draft was created')
                existing = (
                    await uow.execute(
                        sqlalchemy.select(SkillVersion).where(
                            *self._scope(SkillVersion, context),
                            SkillVersion.name == name,
                            SkillVersion.revision == revision,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    if existing.manifest_json != publication['manifest']:
                        raise ValueError('Persisted Skill revision has a conflicting manifest')
                    continue
                # CAS runs first. Database blobs share this transaction; S3 keys
                # are unique and never overwrite retained publications.
                reference = await self.content.put(
                    context, owner_type='skill', owner=name, key=revision, value=publication['file_bytes']
                )
                await uow.execute(
                    sqlalchemy.insert(SkillVersion).values(
                        uuid=str(uuid.uuid4()),
                        workspace_uuid=context.workspace_uuid,
                        instance_uuid=context.instance_uuid,
                        name=name,
                        revision=revision,
                        manifest_json=publication['manifest'],
                        skill_json=skill,
                        content_ref=reference,
                    )
                )

    @staticmethod
    def _migration_skill(skill):
        return json.loads(
            json.dumps(
                {key: value for key, value in skill.items() if key not in _LOCAL_FIELDS},
                ensure_ascii=False,
                default=str,
            )
        )

    async def import_retained_publication(self, context, publication, uow):
        """Import verified legacy bytes without changing a current registry pointer."""
        skill = self._migration_skill(publication['skill'])
        name = SkillStore._validate_skill_name(skill['name'])
        revision = skill['revision']
        SkillStore._validate_revision(revision)
        archive = publication['file_bytes']
        if not isinstance(archive, bytes) or len(archive) > MAX_PUBLICATION_BYTES:
            raise ValueError('Skill migration archive exceeds the database persistence limit')
        existing = (
            await uow.execute(
                sqlalchemy.select(SkillVersion).where(
                    *self._scope(SkillVersion, context), SkillVersion.name == name, SkillVersion.revision == revision
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.manifest_json != publication['manifest'] or existing.skill_json != skill:
                raise ValueError(f'Skill migration conflicts with retained version {name}@{revision}')
            reference = existing.content_ref
        else:
            reference = await self.content.put(context, owner_type='skill', owner=name, key=revision, value=archive)
            await uow.execute(
                sqlalchemy.insert(SkillVersion).values(
                    uuid=str(uuid.uuid4()),
                    workspace_uuid=context.workspace_uuid,
                    instance_uuid=context.instance_uuid,
                    name=name,
                    revision=revision,
                    manifest_json=publication['manifest'],
                    skill_json=skill,
                    content_ref=reference,
                )
            )
        # A checkpoint must not bless a missing/corrupt object-store write or an old target blob.
        if await self.content.get(context, reference, max_bytes=MAX_PUBLICATION_BYTES) != archive:
            raise ValueError(f'Skill migration content differs for {name}@{revision}')

    async def publish_migrated_registry(self, context, skills, uow):
        """Expose the original current pointers only with the final import marker."""
        dialect = self.ap.persistence_mgr.get_db_engine().dialect.name
        insert = sqlite_insert if dialect == 'sqlite' else pg_insert
        for source in skills:
            skill = self._migration_skill(source)
            name, revision = skill['name'], skill['revision']
            version = (
                await uow.execute(
                    sqlalchemy.select(SkillVersion).where(
                        *self._scope(SkillVersion, context),
                        SkillVersion.name == name,
                        SkillVersion.revision == revision,
                    )
                )
            ).scalar_one_or_none()
            if version is None or version.skill_json != skill:
                raise ValueError(f'Skill migration has no verified current version for {name}')
            await uow.execute(
                insert(SkillRegistry)
                .values(
                    uuid=str(uuid.uuid4()),
                    workspace_uuid=context.workspace_uuid,
                    instance_uuid=context.instance_uuid,
                    name=name,
                    current_revision=revision,
                    skill_json=skill,
                )
                .on_conflict_do_nothing(index_elements=['workspace_uuid', 'instance_uuid', 'name'])
            )
            registry = (
                await uow.execute(
                    sqlalchemy.select(SkillRegistry).where(
                        *self._scope(SkillRegistry, context), SkillRegistry.name == name
                    )
                )
            ).scalar_one()
            if registry.current_revision != revision or registry.skill_json != skill:
                raise ValueError(f'Skill migration conflicts with the current database registration for {name}')

    async def call(self, context, namespace: str, method: str, *args, **kwargs):
        if method == 'import_skill_zip':
            return await self._import_zip(context, *args, **kwargs)
        if method == 'list_skills':
            async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
                rows = (
                    (
                        await uow.execute(
                            sqlalchemy.select(SkillRegistry.skill_json)
                            .where(*self._scope(SkillRegistry, context))
                            .order_by(SkillRegistry.updated_at.desc())
                            .limit(1001)
                        )
                    )
                    .scalars()
                    .all()
                )
            if len(rows) > 1000:
                raise ValueError('Skill listing exceeds the configured entry limit')
            skills = []
            retained_bytes = 0
            for skill in rows:
                retained_bytes += len(json.dumps(skill, ensure_ascii=False).encode())
                if retained_bytes > 16 * 1024 * 1024:
                    raise ValueError('Skill listing exceeds the configured text limit')
                skills.append(dict(skill))
            return skills
        if method in {'get_skill', 'get_skill_snapshot'}:
            revision = args[1] if len(args) > 1 else kwargs.get('revision')
            record = await self._record(context, args[0], revision)
            if method == 'get_skill':
                return dict(record['skill']) if record is not None else None
            return await self._materialize(context, namespace, record) if record is not None else None
        if method == 'delete_skill':
            name = SkillStore._validate_skill_name(args[0])
            async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
                result = await uow.execute(
                    sqlalchemy.delete(SkillRegistry).where(
                        *self._scope(SkillRegistry, context), SkillRegistry.name == name
                    )
                )
                if result.rowcount != 1:
                    raise ValueError(f'Skill "{name}" not found')
            return {'deleted': name}
        if method in {'list_skill_resources', 'read_skill_resource'} and (
            getattr(getattr(self.ap, 'box_service', None), 'file_transfer_mode', None) == 'network'
        ):
            content = self.content
            async with self.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
                await self._validate_context(context)
                record = await self._record(context, args[0], kwargs.get('expected_revision'))
                if record is None:
                    raise ValueError(f'Skill "{args[0]}" not found')
                await content._validate(context)
                if method == 'list_skill_resources':
                    content._validate_ref(record['content_ref'])
                else:
                    cache_key, cached, row = await self._resource_archive_row(uow, context, record['content_ref'])
            if method == 'list_skill_resources':
                return await run_blocking_atomic(
                    SkillStore.list_publication_manifest_resources,
                    record['skill'],
                    record['manifest'],
                    *args[1:],
                    **kwargs,
                )
            # Release the database connection before object-store IO and ZIP validation.
            return await self._read_resource_archive(
                cache_key,
                cached,
                row,
                partial(SkillStore.read_publication_resource, record['skill'], record['manifest']),
                *args[1:],
                **kwargs,
            )
        if method in {'list_skill_files', 'read_skill_file', 'list_skill_resources', 'read_skill_resource'}:
            record = await self._record(context, args[0], kwargs.get('expected_revision'))
            if record is None:
                raise ValueError(f'Skill "{args[0]}" not found')
            if getattr(getattr(self.ap, 'box_service', None), 'file_transfer_mode', None) == 'network':
                archive = await self._archive(context, record)

                def read_resource():
                    with tempfile.TemporaryDirectory(prefix='langbot-skill-read-') as temporary:
                        store = SkillStore(temporary)
                        store.restore_skill_publication(record['skill'], record['manifest'], archive, make_current=True)
                        return getattr(store, method)(*args, **kwargs)

                return await run_blocking_atomic(read_resource)
            skill = await self._materialize(context, namespace, record)
            store = self.cache.scoped(namespace)
            if method == 'list_skill_files':
                return await run_blocking_atomic(store._list_skill_files, skill, *args[1:])
            if method == 'read_skill_file':
                return await run_blocking_atomic(store._read_skill_file, skill, *args[1:])
            kwargs['expected_revision'] = skill['revision']
            return await run_blocking_atomic(getattr(store, method), *args, **kwargs)
        current = None
        if method in {'update_skill', 'write_skill_file', 'import_skill_directory'}:
            name = (
                SkillStore._validate_skill_name(args[1].get('name', ''))
                if method == 'import_skill_directory'
                else args[0]
            )
            current = await self._record(context, name)
        current_archive = await self._archive(context, current) if current is not None else None
        if method == 'create_skill' and args[0].get('package_root'):
            self.cache.scoped(namespace)._require_scoped_path(args[0]['package_root'], 'package_root')

        def invoke():
            with tempfile.TemporaryDirectory(prefix='langbot-skill-publish-') as temporary:
                store = SkillStore(temporary)
                if current is not None:
                    store.restore_skill_publication(
                        current['skill'], current['manifest'], current_archive, make_current=True
                    )
                result = getattr(store, method)(*args, **kwargs)
                if method in {'preview_zip_upload', 'scan_import_directory'}:
                    return result, []
                names = (
                    [item['name'] for item in result]
                    if method == 'install_zip_upload'
                    else [args[0] if method == 'write_skill_file' else result['name']]
                )
                return result, [store.export_skill_publication(name) for name in names]

        result, publications = await run_blocking_atomic(invoke)
        if not publications:
            return result
        bases = {
            publication['skill']['name']: current['skill']['revision'] if current is not None else None
            for publication in publications
        }
        await self._publish(context, publications, bases)
        if method == 'write_skill_file':
            return result
        published = [dict(publication['skill']) for publication in publications]
        if method == 'install_zip_upload':
            return [
                dict(skill, **({'source_path': old['source_path']} if 'source_path' in old else {}))
                for skill, old in zip(published, result)
            ]
        return published[0]
