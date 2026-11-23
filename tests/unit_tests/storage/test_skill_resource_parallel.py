"""Real byte verification and bounded workers with transaction-only DB stubs."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
import hashlib
import io
import struct
import threading
from types import SimpleNamespace
import zipfile

import pytest

from langbot.pkg.core import app as app  # Load storage through the normal Core import order.
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.skill.database_repository import DatabaseSkillRepository
from langbot.pkg.storage.content import ContentStore
from langbot.pkg.utils.bounded_executor import BoundedThreadPoolExecutor, blocking_work_scope
from langbot_plugin.skill_store import SkillStore


pytestmark = pytest.mark.skipif(
    not callable(getattr(SkillStore, 'read_publication_resource', None)),
    reason='requires publication resource SDK',
)

CONTEXT = ExecutionContext(
    instance_uuid='instance', workspace_uuid='00000000-0000-0000-0000-000000000001', placement_generation=1
)
GUIDE = 'Verified guide.\n' * 256
PATH = 'references/guide.md'


@pytest.fixture
def publication(tmp_path):
    source = tmp_path / 'source'
    (source / 'references').mkdir(parents=True)
    (source / 'SKILL.md').write_text('---\nname: parallel-check\ndescription: Verify all bytes\n---\nRead the guide.\n')
    (source / PATH).write_text(GUIDE)
    (source / 'payload.bin').write_bytes(b'x' * (2 * 1024 * 1024))
    store = SkillStore(str(tmp_path / 'store'))
    store.import_skill_directory(str(source), {'name': 'parallel-check'}, source_root=str(tmp_path))
    return store.export_skill_publication('parallel-check')


@contextmanager
def executor_for_loop(scope_limit=4, max_pending=128):
    loop = asyncio.get_running_loop()
    previous = loop._default_executor
    executor = BoundedThreadPoolExecutor(max_workers=8, max_pending=max_pending, max_inflight_per_scope=scope_limit)
    loop.set_default_executor(executor)
    try:
        yield executor
    finally:
        loop._default_executor = previous
        executor.shutdown(wait=True)


def cached_repository(publication, executor):
    archive = publication['file_bytes']
    metadata = {'size': len(archive), 'digest': hashlib.sha256(archive).hexdigest()}
    state = {'inside': False, 'events': [], 'metadata': metadata, 'source_reads': 0}

    @asynccontextmanager
    async def transaction(workspace):
        assert workspace == CONTEXT.workspace_uuid and not state['inside']
        state['inside'] = True
        try:
            yield object()
        finally:
            state['inside'] = False

    async def validate(context):
        assert context == CONTEXT and state['inside']
        state['events'].append('before-record')

    async def validate_content(context):
        assert context == CONTEXT and state['inside']
        state['events'].append('after-record')

    async def record(context, name, revision):
        assert context == CONTEXT and name == 'parallel-check' and state['inside']
        assert revision == publication['skill']['revision']
        state['events'].append('record')
        return {'skill': publication['skill'], 'manifest': publication['manifest'], 'content_ref': 'ct1_' + 'a' * 64}

    async def row(_uow, workspace, ref, *, metadata_only=False):
        assert workspace == CONTEXT.workspace_uuid and ref == 'ct1_' + 'a' * 64 and state['inside']
        if metadata_only:
            return dict(state['metadata'])
        return {**state['metadata'], 'backend': 'database', 'value': archive}

    async def read(row, limit):
        assert not state['inside']
        state['source_reads'] += 1
        return await ContentStore._read(content, row, limit)

    content = SimpleNamespace(
        _validate=validate_content, _row=row, _read=read, _validated_value=ContentStore._validated_value
    )
    application = SimpleNamespace(
        persistence_mgr=SimpleNamespace(tenant_uow=transaction),
        storage_mgr=SimpleNamespace(content_store=content),
        box_service=SimpleNamespace(file_transfer_mode='network'),
        blocking_executor=executor,
    )
    repository = DatabaseSkillRepository(application, None, validate)
    repository._record = record
    key = (CONTEXT.instance_uuid, CONTEXT.workspace_uuid, 'ct1_' + 'a' * 64)
    repository._remember_resource_archive(key, archive, metadata)
    return repository, key, state


async def read_resource(repository, publication):
    with blocking_work_scope('skill:parallel-check'):
        return await repository.call(
            CONTEXT,
            'unused',
            'read_skill_resource',
            'parallel-check',
            PATH,
            expected_revision=publication['skill']['revision'],
        )


async def wait_until(predicate):
    deadline = asyncio.get_running_loop().time() + 5
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, 'Worker did not reach the expected checkpoint'
        await asyncio.sleep(0.001)


@pytest.mark.parametrize('scope_limit', [None, 1, 4])
@pytest.mark.asyncio
async def test_cached_read_uses_only_known_parallel_capacity(publication, monkeypatch, scope_limit):
    async def scenario():
        with executor_for_loop(scope_limit or 4) as executor:
            repository, key, state = cached_repository(publication, executor if scope_limit is not None else None)
            content = repository.content
            digest_check = content._validated_value
            sdk_read = SkillStore.read_publication_resource
            seen = []
            barrier = threading.Barrier(2) if scope_limit == 4 else None
            main_thread = threading.get_ident()

            def digest(archive, *args):
                assert not state['inside'] and archive is publication['file_bytes']
                seen.append(('digest', threading.get_ident()))
                if barrier is not None:
                    barrier.wait(timeout=5)
                return digest_check(archive, *args)

            def resource(skill, manifest, archive, *args, **kwargs):
                assert not state['inside'] and archive is publication['file_bytes']
                seen.append(('resource', threading.get_ident()))
                if barrier is not None:
                    barrier.wait(timeout=5)
                return sdk_read(skill, manifest, archive, *args, **kwargs)

            content._validated_value = digest
            monkeypatch.setattr(SkillStore, 'read_publication_resource', staticmethod(resource))
            result = await read_resource(repository, publication)
            assert result['content'] == GUIDE and state['source_reads'] == 0
            assert state['events'] == ['before-record', 'record', 'after-record']
            assert repository._resource_archives[key]['value'] is publication['file_bytes']
            threads = dict(seen)
            assert threads['resource'] != main_thread
            assert (threads['digest'] != main_thread) is (scope_limit == 4)
            snapshot = executor.snapshot()
            assert snapshot['submitted_total'] == (2 if scope_limit == 4 else 1)
            assert snapshot['rejected_total'] == snapshot['inflight'] == 0

    await scenario()


@pytest.mark.asyncio
async def test_cold_read_keeps_the_original_single_worker_path(publication):
    async def scenario():
        with executor_for_loop() as executor:
            repository, key, state = cached_repository(publication, executor)
            repository._discard_resource_archive(key)
            result = await read_resource(repository, publication)
            assert result['content'] == GUIDE and state['source_reads'] == 1
            assert executor.snapshot()['submitted_total'] == 1
            assert executor.snapshot()['rejected_total'] == 0

    await scenario()


@pytest.mark.parametrize('wrong_digest', [False, True])
@pytest.mark.asyncio
async def test_both_checks_finish_and_digest_errors_keep_priority(publication, monkeypatch, wrong_digest):
    archive = publication['file_bytes']
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        member = opened.getinfo('payload.bin')
        filename, extra = struct.unpack_from('<HH', archive, member.header_offset + 26)
        offset = member.header_offset + 30 + filename + extra
    damaged = archive[:offset] + bytes([archive[offset] ^ 1]) + archive[offset + 1 :]

    async def scenario():
        with executor_for_loop() as executor:
            repository, key, state = cached_repository(publication, executor)
            repository._resource_archives[key]['value'] = damaged
            if not wrong_digest:
                state['metadata']['digest'] = hashlib.sha256(damaged).hexdigest()
                repository._resource_archives[key]['digest'] = state['metadata']['digest']
            sdk_read = SkillStore.read_publication_resource
            sdk_errors = []

            def resource(*args, **kwargs):
                try:
                    return sdk_read(*args, **kwargs)
                except Exception as exc:
                    sdk_errors.append(exc)
                    raise

            monkeypatch.setattr(SkillStore, 'read_publication_resource', staticmethod(resource))
            expected = ValueError if wrong_digest else zipfile.BadZipFile
            with pytest.raises(expected) as failure:
                await read_resource(repository, publication)
            if wrong_digest:
                assert 'Persisted content failed digest verification' in str(failure.value)
            assert len(sdk_errors) == 1 and isinstance(sdk_errors[0], zipfile.BadZipFile)
            assert key not in repository._resource_archives and repository._resource_archive_bytes == 0
            assert executor.snapshot()['submitted_total'] == 2
            assert executor.snapshot()['inflight'] == 0

    await scenario()


@pytest.mark.asyncio
async def test_global_capacity_rejection_retries_only_the_unexecuted_check(publication, monkeypatch):
    async def scenario():
        with executor_for_loop(max_pending=0) as executor:
            release_occupied, release_digest = threading.Event(), threading.Event()
            occupied = [executor.submit(release_occupied.wait, 5) for _ in range(7)]
            repository, _key, _state = cached_repository(publication, executor)
            content = repository.content
            digest_check = content._validated_value
            sdk_read = SkillStore.read_publication_resource
            calls = []

            def digest(*args):
                calls.append('digest')
                assert release_digest.wait(5)
                return digest_check(*args)

            def resource(*args, **kwargs):
                calls.append('resource')
                return sdk_read(*args, **kwargs)

            content._validated_value = digest
            monkeypatch.setattr(SkillStore, 'read_publication_resource', staticmethod(resource))
            request = asyncio.create_task(read_resource(repository, publication))
            try:
                await wait_until(lambda: executor.snapshot()['rejected_total'] == 1 and calls == ['digest'])
                assert calls == ['digest']
                release_digest.set()
                result = await request
                assert result['content'] == GUIDE and calls == ['digest', 'resource']
                snapshot = executor.snapshot()
                assert snapshot['submitted_total'] == 9
                assert snapshot['global_rejected_total'] == 1 and snapshot['scope_rejected_total'] == 0
            finally:
                release_digest.set()
                release_occupied.set()
                await asyncio.gather(
                    request, *(asyncio.wrap_future(future) for future in occupied), return_exceptions=True
                )
            assert executor.snapshot()['inflight'] == 0

    await scenario()


@pytest.mark.asyncio
async def test_repeated_cancel_waits_for_both_workers_before_unlock_and_cache_removal(publication, monkeypatch):
    async def scenario():
        with executor_for_loop() as executor:
            repository, key, _state = cached_repository(publication, executor)
            begun = [threading.Event(), threading.Event()]
            release = [threading.Event(), threading.Event()]
            finished = [threading.Event(), threading.Event()]
            digest_check = repository.content._validated_value
            sdk_read = SkillStore.read_publication_resource
            lock = asyncio.Lock()

            def digest(*args):
                begun[0].set()
                assert release[0].wait(5)
                result = digest_check(*args)
                finished[0].set()
                return result

            def resource(*args, **kwargs):
                begun[1].set()
                assert release[1].wait(5)
                result = sdk_read(*args, **kwargs)
                finished[1].set()
                return result

            async def locked_read():
                async with lock:
                    return await read_resource(repository, publication)

            repository.content._validated_value = digest
            monkeypatch.setattr(SkillStore, 'read_publication_resource', staticmethod(resource))
            request = asyncio.create_task(locked_read())
            try:
                await wait_until(lambda: all(event.is_set() for event in begun))
                request.cancel()
                await asyncio.sleep(0)
                request.cancel()
                await asyncio.sleep(0)
                assert not request.done() and lock.locked() and key in repository._resource_archives
                release[0].set()
                await wait_until(finished[0].is_set)
                assert not request.done() and lock.locked()
                release[1].set()
                with pytest.raises(asyncio.CancelledError):
                    await request
            finally:
                for event in release:
                    event.set()
                await asyncio.gather(request, return_exceptions=True)
            assert all(event.is_set() for event in finished)
            assert not lock.locked() and key not in repository._resource_archives
            assert repository._resource_archive_bytes == executor.snapshot()['inflight'] == 0

    await scenario()
