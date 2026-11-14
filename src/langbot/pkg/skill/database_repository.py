from __future__ import annotations

import hashlib
import json
import tempfile
import uuid

import sqlalchemy
from langbot_plugin.skill_store import SkillRevisionConflictError, SkillRevisionNotFoundError, SkillStore
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..entity.persistence.skill import SkillRegistry, SkillVersion
from ..utils.bounded_executor import run_blocking_atomic


MAX_PUBLICATION_BYTES = 64 * 1024 * 1024
_LOCAL_FIELDS = {'package_root', 'manifest_path', 'source_path'}


class DatabaseSkillRepository:
    """Use the database as authority and the SDK store only for disposable trees."""

    def __init__(self, ap, cache: SkillStore):
        self.ap = ap
        self.cache = cache

    @property
    def content(self):
        return self.ap.storage_mgr.content_store

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
            }

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

    async def get_package(self, context, name: str, revision: str | None = None) -> dict:
        record = await self._record(context, name, revision)
        if record is None:
            raise ValueError(f'Skill "{name}" not found')
        content = await self._archive(context, record)
        return {
            'content': content,
            'revision': record['skill']['revision'],
            'manifest': record['manifest'],
            'sha256': hashlib.sha256(content).hexdigest(),
            'size': len(content),
            'filename': f'{record["skill"]["name"]}.zip',
        }

    async def _import_zip(self, context, file_bytes: bytes, data: dict, *, base_revision: str | None) -> dict:
        with tempfile.TemporaryDirectory(prefix='langbot-skill-draft-') as temporary:
            store = SkillStore(temporary + '/store')
            source, payload = await run_blocking_atomic(store._prepare_skill_zip, file_bytes, temporary, data)
            current = await self._record(context, payload['name'])
            archive = await self._archive(context, current) if current is not None else None

            def publish():
                if current is not None:
                    store.restore_skill_publication(current['skill'], current['manifest'], archive, make_current=True)
                result = store.import_skill_directory(
                    source, payload, source_root=temporary, base_revision=base_revision
                )
                return store.export_skill_publication(result['name'])

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
