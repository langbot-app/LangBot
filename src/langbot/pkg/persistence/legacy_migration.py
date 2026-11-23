"""Short, fenced tenant transactions for one-time filesystem imports."""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import math
import re
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..api.http.context import ExecutionContext
from ..entity.persistence.metadata import WorkspaceMetadata


_LEASE_SECONDS = 300
_MAX_STATE_BYTES = 1024 * 1024


def require_import_runtime(ap):
    runtime = getattr(ap, 'box_service', None)
    if runtime is not None and runtime.enabled and runtime.file_transfer_mode == 'network' and not runtime.available:
        raise RuntimeError('Complete the network Box handshake before importing legacy content')


class MigrationBusyError(RuntimeError):
    pass


class MigrationLeaseLostError(RuntimeError):
    pass


class WorkspaceMigration:
    """Own an import lease; business writes and each checkpoint commit together.

    A conditional UPDATE locks the metadata row for the whole short transaction.
    An expired lease cannot be taken over until that transaction commits, and
    the previous owner must acquire its fence again before making another write.
    """

    def __init__(self, ap, context: ExecutionContext, domain: str):
        if not isinstance(context, ExecutionContext):
            raise ValueError('Filesystem migration requires a trusted execution context')
        if (
            not context.instance_uuid.strip()
            or not context.workspace_uuid.strip()
            or isinstance(context.placement_generation, bool)
            or not isinstance(context.placement_generation, int)
            or context.placement_generation <= 0
        ):
            raise ValueError('Filesystem migration requires an explicit fenced Workspace')
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,80}', domain):
            raise ValueError('Invalid filesystem migration domain')
        self.ap, self.context = ap, context
        self.key = f'{domain}:{hashlib.sha256(context.instance_uuid.encode()).hexdigest()}'
        self.owner = str(uuid.uuid4())
        self.completed = False
        self.progress = {}
        self._acquired = False

    def _where(self):
        return (
            WorkspaceMetadata.workspace_uuid == self.context.workspace_uuid,
            WorkspaceMetadata.key == self.key,
        )

    async def _validate_context(self):
        binding = await self.ap.workspace_service.get_execution_binding(
            self.context.workspace_uuid, expected_generation=self.context.placement_generation
        )
        if any(
            getattr(binding, name, None) != getattr(self.context, name)
            for name in ('instance_uuid', 'workspace_uuid', 'placement_generation')
        ):
            raise ValueError('Filesystem migration belongs to a stale Workspace placement')

    async def _now(self, uow):
        dialect = self.ap.persistence_mgr.get_db_engine().dialect.name
        if dialect == 'postgresql':
            value = (await uow.execute(sa.select(sa.func.now()))).scalar_one()
            if value.tzinfo is None:
                value = value.replace(tzinfo=dt.timezone.utc)
            return value.timestamp()
        if dialect == 'sqlite':
            return float((await uow.execute(sa.select(sa.func.strftime('%s', 'now')))).scalar_one())
        raise ValueError('Filesystem migration requires PostgreSQL or SQLite')

    @staticmethod
    def _encode(state):
        value = json.dumps(state, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        if len(value.encode()) > _MAX_STATE_BYTES:
            raise ValueError('Filesystem migration checkpoint exceeds its size limit')
        return value

    def _decode(self, value):
        try:
            state = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError('Filesystem migration checkpoint is corrupt') from exc
        if (
            not isinstance(state, dict)
            or type(state.get('schema')) is not int
            or state.get('schema') != 1
            or state.get('instance_uuid') != self.context.instance_uuid
            or state.get('status') not in {'pending', 'running', 'failed', 'completed'}
            or not isinstance(state.get('progress'), dict)
            or (state.get('owner') is not None and (not isinstance(state['owner'], str) or not state['owner']))
            or isinstance(state.get('lease_until'), bool)
            or not isinstance(state.get('lease_until'), (int, float))
            or not math.isfinite(state['lease_until'])
            or state['lease_until'] < 0
            or (state['status'] == 'completed' and (state['owner'] is not None or state['lease_until'] != 0))
            or (state['status'] == 'running' and (state['owner'] is None or state['lease_until'] <= 0))
            or (state['status'] in {'pending', 'failed'} and state['owner'] is not None)
        ):
            raise ValueError('Filesystem migration checkpoint is invalid')
        return state

    async def _read(self, uow):
        row = (await uow.execute(sa.select(WorkspaceMetadata.value).where(*self._where()))).first()
        if row is None:
            return None
        if row[0] is None:
            raise ValueError('Filesystem migration checkpoint is corrupt')
        return row[0]

    async def _cas(self, uow, old, state):
        result = await uow.execute(
            sa.update(WorkspaceMetadata)
            .where(*self._where(), WorkspaceMetadata.value == old)
            .values(value=self._encode(state))
        )
        if result.rowcount != 1:
            raise MigrationLeaseLostError('Filesystem migration ownership changed')

    async def checkpoint(self):
        """Inspect completion before deciding whether an old volume is needed."""
        await self._validate_context()
        async with self.ap.persistence_mgr.tenant_uow(self.context.workspace_uuid) as uow:
            value = await self._read(uow)
        return self._decode(value) if value is not None else None

    async def __aenter__(self):
        await self._validate_context()
        async with self.ap.persistence_mgr.tenant_uow(self.context.workspace_uuid) as uow:
            now = await self._now(uow)
            old = await self._read(uow)
            if old is None:
                state = {
                    'schema': 1,
                    'instance_uuid': self.context.instance_uuid,
                    'status': 'pending',
                    'owner': None,
                    'lease_until': 0,
                    'progress': {},
                }
                insert = (
                    sqlite_insert if self.ap.persistence_mgr.get_db_engine().dialect.name == 'sqlite' else pg_insert
                )
                await uow.execute(
                    insert(WorkspaceMetadata)
                    .values(workspace_uuid=self.context.workspace_uuid, key=self.key, value=self._encode(state))
                    .on_conflict_do_nothing(index_elements=['workspace_uuid', 'key'])
                )
                old = await self._read(uow)
            state = self._decode(old)
            self.progress = state['progress']
            if state['status'] == 'completed':
                self.completed = True
                return self
            if state['owner'] is not None and state['lease_until'] > now:
                raise MigrationBusyError('Another Core owns this filesystem migration; retry after it finishes')
            state.update(status='running', owner=self.owner, lease_until=now + _LEASE_SECONDS)
            state.pop('failure', None)
            await self._cas(uow, old, state)
        self._acquired = True
        return self

    @contextlib.asynccontextmanager
    async def transaction(self, *, complete=False):
        if not self._acquired or self.completed:
            raise MigrationLeaseLostError('Filesystem migration has no active owner')
        await self._validate_context()
        async with self.ap.persistence_mgr.tenant_uow(self.context.workspace_uuid) as uow:
            now = await self._now(uow)
            old = await self._read(uow)
            state = self._decode(old)
            if state['owner'] != self.owner or state['lease_until'] <= now:
                raise MigrationLeaseLostError('Filesystem migration lease expired or changed owner')
            state['lease_until'] = now + _LEASE_SECONDS
            await self._cas(uow, old, state)
            locked_value = self._encode(state)
            # The CAS holds the row write lock through business writes and checkpoint.
            yield uow, state['progress']
            state['status'] = 'completed' if complete else 'running'
            if complete:
                state.update(owner=None, lease_until=0)
            await self._cas(uow, locked_value, state)
        self.progress = state['progress']
        self.completed = complete

    async def renew(self):
        async with self.transaction():
            pass

    async def __aexit__(self, exc_type, exc, traceback):
        if not self._acquired or self.completed:
            return
        try:
            async with self.ap.persistence_mgr.tenant_uow(self.context.workspace_uuid) as uow:
                old = await self._read(uow)
                state = self._decode(old)
                if state['owner'] != self.owner:
                    return
                state.update(owner=None, lease_until=0, status='failed' if exc_type else 'pending')
                if exc_type:
                    state['failure'] = exc_type.__name__
                await self._cas(uow, old, state)
        except Exception:
            if exc_type is None:
                raise
            self.ap.logger.exception('Failed to release filesystem migration owner')
