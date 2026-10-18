"""Image reference contracts apply to ORM and Core writes, including new callers."""

import json

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from langbot.pkg.entity.persistence.agent_run import AgentRun, AgentRunEvent
from langbot.pkg.entity.persistence.event_log import EventLog
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage
from langbot.pkg.entity.persistence.transcript import Transcript
from langbot.pkg.persistence.media import MediaReferenceText
from langbot.pkg.persistence.tenant_uow import ScopedSessionTransactionError, _validate_scoped_statement_call


class PayloadBase(DeclarativeBase):
    pass


class Payload(PayloadBase):
    __tablename__ = 'payload'
    id = sa.Column(sa.Integer, primary_key=True)
    content = sa.Column(MediaReferenceText)


@pytest.fixture
async def engine():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(PayloadBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('writer', ['orm', 'insert', 'update'])
@pytest.mark.parametrize(
    'image',
    [
        {'type': 'Image', 'base64': 'eA=='},
        {'type': 'Image', 'url': 'data:image/png;base64,eA=='},
        {'type': 'image_base64', 'image_base64': 'eA=='},
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,eA=='}},
        {'type': 'image', 'image_url': 'data:image/png;base64,eA=='},
    ],
)
async def test_unprocessed_images_are_rejected_at_the_bind_boundary(engine, writer, image):
    content = json.dumps({'nested': [image]})
    async with engine.begin() as conn:
        await conn.execute(sa.insert(Payload).values(id=1, content='original'))
    with pytest.raises(sa.exc.StatementError, match='use MediaCache.externalize_chain_dump'):
        if writer == 'orm':
            async with AsyncSession(engine) as session:
                session.add(Payload(id=2, content=content))
                await session.commit()
        else:
            statement = (
                sa.insert(Payload).values(id=2, content=content)
                if writer == 'insert'
                else sa.update(Payload).where(Payload.id == 1).values(content=content)
            )
            async with engine.begin() as conn:
                await conn.execute(statement)
    async with engine.connect() as conn:
        assert (await conn.execute(sa.select(Payload.content))).scalars().all() == ['original']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'content',
    [
        None,
        'plain text',
        '{historical invalid JSON',
        json.dumps({'type': 'Plain', 'text': 'base64 is a transport encoding'}),
        json.dumps({'type': 'Image', 'url': 'https://example.com/image.png'}),
        json.dumps({'type': 'Image', 'url': '/api/v1/files/media/hash.png', 'base64': None}),
    ],
)
async def test_plain_text_and_references_round_trip_unchanged(engine, content):
    async with AsyncSession(engine) as session:
        session.add(Payload(id=1, content=content))
        await session.commit()
    async with engine.connect() as conn:
        assert (await conn.execute(sa.select(Payload.content))).scalar_one() == content


@pytest.mark.asyncio
async def test_legacy_images_can_be_read_compared_and_redacted(engine):
    content = json.dumps({'type': 'Image', 'base64': 'eA=='})
    async with engine.begin() as conn:
        # Simulate a row created before the contract was introduced.
        await conn.execute(sa.text('INSERT INTO payload (id, content) VALUES (1, :content)'), {'content': content})
        assert (
            await conn.execute(sa.select(Payload.content).where(Payload.content == content))
        ).scalar_one() == content
        assert (await conn.execute(sa.select(Payload.id).where(Payload.content.like('%base64%')))).scalar_one() == 1
        updated = await conn.execute(
            sa.update(Payload).where(Payload.content == content).values(content='{"type": "Image", "base64": null}')
        )
        assert updated.rowcount == 1


@pytest.mark.parametrize('dialect', [sqlite.dialect(), postgresql.dialect()], ids=['sqlite', 'postgresql'])
def test_contract_keeps_text_schema_and_handles_escaped_json_keys(dialect):
    column_type = MediaReferenceText()
    assert column_type.compile(dialect=dialect) == 'TEXT'
    process = column_type.dialect_impl(dialect).bind_processor(dialect)
    with pytest.raises(ValueError, match='Inline images cannot be persisted'):
        process(r'{"type": "Image", "base\u00364": "eA=="}')


@pytest.mark.parametrize(
    'model, fields',
    [
        (MonitoringMessage, ['message_content', 'variables']),
        (EventLog, ['input_json', 'metadata_json']),
        (AgentRun, ['metadata_json']),
        (AgentRunEvent, ['data_json', 'metadata_json']),
        (Transcript, ['content_json', 'attachment_refs_json', 'metadata_json']),
    ],
)
def test_conversation_payload_columns_declare_the_contract(model, fields):
    for field in fields:
        assert isinstance(model.__table__.c[field].type, MediaReferenceText), f'{model.__tablename__}.{field}'


def test_tenant_queries_admit_only_the_exact_trusted_media_type():
    _validate_scoped_statement_call((sa.select(Payload.content),), {})

    class UntrustedMediaReferenceText(MediaReferenceText):
        pass

    for column_type in (UntrustedMediaReferenceText(), MediaReferenceText(collation=sa.sql.quoted_name('x', False))):
        with pytest.raises(ScopedSessionTransactionError):
            _validate_scoped_statement_call((sa.select(sa.column('content', column_type)),), {})
