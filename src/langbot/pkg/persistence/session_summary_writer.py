"""Transaction-bound message counts and replaceable ingress credits."""

import datetime
import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from ..entity.persistence.monitoring import MonitoringSession, MonitoringSessionReceipt
from .datetime_utils import as_naive_utc
from .session_summary_contract import SessionSummaryChange, message_source_key


SESSION_KEY = ['workspace_uuid', 'bot_id', 'session_id']
RECEIPT_KEY = ['workspace_uuid', 'bot_id', 'source_key']


def message_summary_change(workspace: str, row) -> SessionSummaryChange:
    """Use the same stored message facts for live writes and historical repair."""
    return SessionSummaryChange(
        workspace=workspace,
        bot_id=row['bot_id'],
        session_id=row['session_id'] or '',
        source_key=message_source_key(row['id']),
        event_id=row['event_id'],
        timestamp=row['timestamp'],
        bot_name=row['bot_name'] or '',
        pipeline_id=row['pipeline_id'] or '',
        pipeline_name=row['pipeline_name'] or '',
        platform=row['platform'],
        user_id=row['user_id'],
        user_name=row['user_name'],
        role=row['role'] or 'user',
    )


def ingress_summary_change(workspace: str, row) -> SessionSummaryChange:
    """Project persisted ingress identities and the first route with a target."""
    metadata = json.loads(row['metadata_json'] or '{}')
    if not isinstance(metadata, dict):
        raise ValueError('Ingress metadata must be a JSON object')
    route = next(
        (route for route in metadata.get('routes') or () if isinstance(route, dict) and route.get('target_uuid')),
        {},
    )
    return SessionSummaryChange(
        workspace=workspace,
        bot_id=row['bot_id'],
        session_id=row['conversation_id'] or '',
        source_key=f'event:{row["event_id"]}',
        timestamp=row['event_time'] or row['created_at'],
        bot_name=metadata.get('bot_name') or '',
        pipeline_id=route.get('target_uuid') or '',
        pipeline_name=route.get('target_type') or '',
        platform=metadata.get('platform'),
        user_id=row['actor_id'],
        user_name=row['actor_name'],
    )


SNAPSHOT_FIELDS = ('bot_name', 'platform', 'user_id', 'user_name', 'pipeline_id', 'pipeline_name')


def _snapshot(change):
    return {
        'source_key': change.source_key,
        'timestamp': as_naive_utc(change.timestamp).isoformat(),
        'role': change.role,
        **{field: getattr(change, field) for field in SNAPSHOT_FIELDS},
    }


def _rank(snapshot):
    if snapshot['source_key'] is None:
        return (-1, '', b'')
    return (int(snapshot['role'] != 'assistant'), snapshot['timestamp'], snapshot['source_key'].encode('utf-8'))


class SessionSummaryWriter:
    def __init__(self, dialect: str):
        self._insert = {'postgresql': postgresql.insert, 'sqlite': sqlite.insert}[dialect]
        self._collation = 'C' if dialect == 'postgresql' else 'BINARY'

    @staticmethod
    def _scope(model, workspace, bot_id=None, identity=None):
        conditions = [model.workspace_uuid == workspace]
        if bot_id is not None:
            conditions.append(model.bot_id == bot_id)
        if identity is not None:
            conditions.append(model.session_id == identity)
        return conditions

    async def _lock_event(self, session, workspace, bot_id, event_id, timestamp):
        """Serialize an event even when it has not arrived yet."""
        receipt = MonitoringSessionReceipt
        return (
            (
                await session.execute(
                    self._insert(receipt)
                    .values(
                        workspace_uuid=workspace,
                        bot_id=bot_id,
                        source_key=f'event:{event_id}',
                        event_id=event_id,
                        role='event',
                        covered=False,
                        timestamp=timestamp,
                    )
                    .on_conflict_do_update(
                        index_elements=RECEIPT_KEY,
                        set_={
                            'timestamp': sa.case((receipt.timestamp < timestamp, timestamp), else_=receipt.timestamp)
                        },
                    )
                    .returning(receipt.session_id, receipt.covered)
                )
            )
            .mappings()
            .one()
        )

    async def _cover_event(self, session, workspace, bot_id, event_id, timestamp):
        previous = await self._lock_event(session, workspace, bot_id, event_id, timestamp)
        receipt = MonitoringSessionReceipt
        await session.execute(
            sa.update(receipt)
            .where(*self._scope(receipt, workspace, bot_id), receipt.source_key == f'event:{event_id}')
            .values(covered=True, session_id=None, candidate_snapshot=None, source_timestamp=None)
        )
        return previous['session_id']

    async def _lock_summaries(self, session, workspace, identities, change=None):
        """Lock sorted (bot, session) keys before message receipt FK checks."""
        model = MonitoringSession
        for bot_id, identity in sorted(identities):
            key = self._scope(model, workspace, bot_id, identity)
            if change is not None and (bot_id, identity) == (change.bot_id, change.session_id):
                timestamp = as_naive_utc(change.timestamp)
                # Updating the key takes FOR UPDATE, and recreates a deleted row.
                await session.execute(
                    self._insert(model)
                    .values(
                        workspace_uuid=workspace,
                        bot_id=bot_id,
                        session_id=identity,
                        bot_name='',
                        pipeline_id='',
                        pipeline_name='',
                        message_count=0,
                        source_count=0,
                        start_time=timestamp,
                        last_activity=timestamp,
                        is_active=True,
                    )
                    .on_conflict_do_update(index_elements=SESSION_KEY, set_={'session_id': identity})
                )
            else:
                await session.execute(sa.select(model.session_id).where(*key).with_for_update())
            row = (await session.execute(sa.select(model.__table__).where(*key))).mappings().one_or_none()
            if row is not None:
                # Legacy values are an unranked fallback, seeded one row at a time.
                # Never promote a replaceable candidate into the immutable base.
                if row['base_snapshot'] is None and row['metadata_source_key'] is None and row['message_count'] > 0:
                    fallback = {
                        'source_key': None,
                        'timestamp': None,
                        'role': None,
                        **{field: row[field] for field in SNAPSHOT_FIELDS},
                    }
                    await session.execute(sa.update(model).where(*key).values(base_snapshot=json.dumps(fallback)))

    async def _merge_base(self, session, workspace, bot_id, identity, snapshot):
        """Fold immutable messages and expired ingress under the summary lock."""
        model = MonitoringSession
        key = self._scope(model, workspace, bot_id, identity)
        encoded = (await session.execute(sa.select(model.base_snapshot).where(*key))).scalar_one()
        previous = json.loads(encoded) if encoded else None
        if previous is None or _rank(snapshot) >= _rank(previous):
            await session.execute(sa.update(model).where(*key).values(base_snapshot=json.dumps(snapshot)))

    async def _refresh(self, session, workspace, bot_id, identity, delta=0, *, backfill=False, observed=None):
        model, receipt = MonitoringSession, MonitoringSessionReceipt
        key = self._scope(model, workspace, bot_id, identity)
        row = (await session.execute(sa.select(model.__table__).where(*key))).mappings().one()
        candidate = (
            await session.execute(
                sa.select(receipt.candidate_snapshot)
                .where(
                    *self._scope(receipt, workspace, bot_id, identity),
                    receipt.candidate_snapshot.is_not(None),
                )
                .order_by(receipt.source_timestamp.desc(), receipt.source_key.collate(self._collation).desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        snapshots = [json.loads(value) for value in (row['base_snapshot'], candidate) if value is not None]
        count = row['source_count'] + delta
        displayed = max(row['message_count'], count) if backfill else row['message_count'] + delta
        if count < 0 or displayed < 0:
            raise ValueError('Session summary counts cannot be negative')
        values = dict(source_count=count, message_count=displayed)
        if snapshots:
            selected = max(snapshots, key=_rank)
            values.update({field: selected[field] for field in SNAPSHOT_FIELDS})
            values.update(
                metadata_source_key=selected['source_key'],
                metadata_role=selected['role'],
                metadata_timestamp=(
                    datetime.datetime.fromisoformat(selected['timestamp']) if selected['timestamp'] else None
                ),
            )
        if observed is not None:
            values.update(
                start_time=min(row['start_time'], observed), last_activity=max(row['last_activity'], observed)
            )
        await session.execute(sa.update(model).where(*key).values(**values))
        if count == 0 and displayed == 0:
            await session.execute(sa.delete(model).where(*key))

    async def link_event(self, session: AsyncSession, workspace: str, bot_id: str, message_id: str, event_id: str):
        """Keep the message credit and retire an uncovered ingress credit once."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        state = await self._lock_event(session, workspace, bot_id, event_id, timestamp)
        receipt = MonitoringSessionReceipt
        predicates = [*self._scope(receipt, workspace, bot_id), receipt.source_key == f'message:{message_id}']
        statement = sa.select(receipt.session_id, receipt.event_id, receipt.role).where(*predicates)
        message = (await session.execute(statement)).mappings().one_or_none()
        if message is None or message['role'] == 'assistant':
            return
        identities = {(bot_id, message['session_id'])}
        owner = state['session_id']
        if owner is not None:
            identities.add((bot_id, owner))
        # The same lock order as apply_once also serializes a message replay.
        await self._lock_summaries(session, workspace, identities)
        message = (await session.execute(statement.with_for_update())).mappings().one_or_none()
        if message is None:
            return
        if message['event_id'] is not None:
            if message['event_id'] != event_id:
                raise ValueError('A message cannot be linked to two events')
            return
        await session.execute(
            sa.update(receipt)
            .where(*self._scope(receipt, workspace, bot_id), receipt.source_key == f'event:{event_id}')
            .values(covered=True, session_id=None, candidate_snapshot=None, source_timestamp=None)
        )
        await session.execute(sa.update(receipt).where(*predicates).values(event_id=event_id, timestamp=timestamp))
        if owner is not None:
            await self._refresh(session, workspace, bot_id, owner, -1)

    async def apply_once(self, session: AsyncSession, change: SessionSummaryChange, *, backfill: bool = False) -> bool:
        """Project a source in its transaction; distinct message rows always count."""
        if not change.session_id:
            return False
        receipt = MonitoringSessionReceipt
        workspace, bot_id, identity = change.workspace, change.bot_id, change.session_id
        timestamp = as_naive_utc(change.timestamp)
        deltas = {}
        ingress = change.source_key.startswith('event:')
        if ingress:
            state = await self._lock_event(
                session, workspace, bot_id, change.source_key.removeprefix('event:'), timestamp
            )
            if state['covered']:
                return False
            if state['session_id'] is not None and state['session_id'] != identity:
                raise ValueError('An ingress event cannot belong to two conversations')
            claimed = state['session_id'] is None
        elif change.role != 'assistant':
            # Legacy message.id matching is part of the historical detail contract.
            for event_id in sorted({change.source_key.removeprefix('message:'), change.event_id} - {None}):
                owner = await self._cover_event(session, workspace, bot_id, event_id, timestamp)
                if owner is not None:
                    deltas[owner] = deltas.get(owner, 0) - 1
        await self._lock_summaries(session, workspace, {(bot_id, key) for key in deltas} | {(bot_id, identity)}, change)
        if ingress:
            await session.execute(
                sa.update(receipt)
                .where(*self._scope(receipt, workspace, bot_id), receipt.source_key == change.source_key)
                .values(
                    session_id=identity, candidate_snapshot=json.dumps(_snapshot(change)), source_timestamp=timestamp
                )
            )
        else:
            result = await session.execute(
                self._insert(receipt)
                .values(
                    workspace_uuid=workspace,
                    bot_id=bot_id,
                    session_id=identity,
                    source_key=change.source_key,
                    event_id=change.event_id,
                    role=change.role,
                    covered=False,
                    timestamp=timestamp,
                )
                .on_conflict_do_nothing(index_elements=RECEIPT_KEY)
            )
            claimed = bool(result.rowcount)
            if claimed:
                await self._merge_base(session, workspace, bot_id, identity, _snapshot(change))
            else:
                previous = (
                    await session.execute(
                        sa.select(receipt.session_id, receipt.role, receipt.event_id).where(
                            *self._scope(receipt, workspace, bot_id), receipt.source_key == change.source_key
                        )
                    )
                ).one()
                if tuple(previous) != (identity, change.role, change.event_id):
                    raise ValueError('A summary message identity cannot change')
        deltas[identity] = deltas.get(identity, 0) + int(claimed)
        for owner, delta in sorted(deltas.items()):
            await self._refresh(
                session,
                workspace,
                bot_id,
                owner,
                delta,
                backfill=backfill,
                observed=timestamp if owner == identity else None,
            )
        return claimed

    async def expire_ingress(self, session: AsyncSession, workspace: str, cutoff, keys) -> int:
        """Seal expired candidates before deleting their event anchors, in one transaction."""
        if not keys:
            return 0
        receipt = MonitoringSessionReceipt
        rows = (
            (
                await session.execute(
                    sa.select(receipt.__table__)
                    .where(
                        receipt.workspace_uuid == workspace,
                        receipt.source_key.startswith('event:'),
                        receipt.timestamp < cutoff,
                        sa.tuple_(receipt.bot_id, receipt.source_key).in_(keys),
                    )
                    .order_by(receipt.bot_id, receipt.source_key)
                    .with_for_update(skip_locked=True)
                )
            )
            .mappings()
            .all()
        )
        owners = {(row['bot_id'], row['session_id']) for row in rows if row['session_id'] is not None}
        await self._lock_summaries(session, workspace, owners)
        for row in rows:
            if row['candidate_snapshot'] is not None:
                await self._merge_base(
                    session, workspace, row['bot_id'], row['session_id'], json.loads(row['candidate_snapshot'])
                )
            await session.execute(
                sa.delete(receipt).where(
                    *self._scope(receipt, workspace, row['bot_id']), receipt.source_key == row['source_key']
                )
            )
        for bot_id, identity in sorted(owners):
            await self._refresh(session, workspace, bot_id, identity)
        return len(rows)
