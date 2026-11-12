"""Workspace failure alerts against a real SQLite schema.

Signals are fed straight into the worker's handler and the periodic pass is
called directly, so thresholds, incident dedupe, delivery claims, reminders,
resolution and every notification channel are exercised end to end.
"""

from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.alerts import service as alert_module
from langbot.pkg.alerts.service import AlertService
from langbot.pkg.entity.persistence import alert as alert_entity
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.webhook import Webhook
from langbot.pkg.entity.persistence.workspace import WorkspaceMembership
from langbot.pkg.notification.email import EmailSendResult

pytestmark = pytest.mark.asyncio

WS = '00000000-0000-0000-0000-0000000000a1'
OWNER = '00000000-0000-0000-0000-0000000000b1'
ADMIN = '00000000-0000-0000-0000-0000000000b2'
VIEWER = '00000000-0000-0000-0000-0000000000b3'


class _Persistence:
    def __init__(self, engine) -> None:
        self.engine = engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result


class _Email:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.sent: list[dict] = []

    def capability(self):
        return {'enabled': self.enabled, 'provider': 'smtp' if self.enabled else None}

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return EmailSendResult(status='sent', provider='smtp')


class _Space:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.calls: list[tuple[str, dict]] = []

    async def get_valid_access_token(self, login: str):
        return f'token-for-{login}'

    async def send_alert_email(self, token: str, payload: dict):
        self.calls.append((token, payload))
        return self.status, {'msg': 'quota' if self.status == 429 else ''}


class _Pusher:
    def __init__(self) -> None:
        self.events: list[tuple[list, dict]] = []

    async def deliver_event(self, webhooks, payload):
        self.events.append((webhooks, payload))
        return [True] * len(webhooks)


@pytest.fixture
async def env(tmp_path, monkeypatch):
    monkeypatch.setattr(alert_module, 'FIRED_GRACE_SECONDS', 0)
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "alerts.db"}')
    tables = [
        Base.metadata.tables[name]
        for name in (
            'users',
            'workspace_memberships',
            'webhooks',
            'alert_settings',
            'alert_incidents',
            'alert_deliveries',
        )
    ]
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
        for uuid, email, account_type in (
            (OWNER, 'owner@example.com', 'local'),
            (ADMIN, 'admin@example.com', 'space'),
            (VIEWER, 'viewer@example.com', 'local'),
        ):
            await connection.execute(
                sqlalchemy.insert(User).values(
                    uuid=uuid,
                    user=email,
                    normalized_email=email,
                    password='x',
                    account_type=account_type,
                    space_refresh_token='refresh' if account_type == 'space' else None,
                )
            )
        for index, (account, role) in enumerate(((OWNER, 'owner'), (ADMIN, 'admin'), (VIEWER, 'viewer'))):
            await connection.execute(
                sqlalchemy.insert(WorkspaceMembership).values(
                    uuid=f'00000000-0000-0000-0000-0000000000c{index}',
                    workspace_uuid=WS,
                    account_uuid=account,
                    role=role,
                    status='active',
                    source='local',
                )
            )
        await connection.execute(
            sqlalchemy.insert(Webhook).values(id=7, workspace_uuid=WS, name='ops', url='https://hooks.example/x')
        )

    email = _Email()
    space = _Space()
    pusher = _Pusher()
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'alerts': {'enabled': True}, 'api': {}}),
        persistence_mgr=_Persistence(engine),
        email_service=email,
        space_service=space,
        webhook_pusher=pusher,
        workspace_service=SimpleNamespace(get_workspace=_workspace),
        logger=SimpleNamespace(warning=lambda *a, **k: None),
    )
    service = AlertService(ap)
    service._queue = asyncio.Queue()
    # Alerts are opt-in; most tests exercise an enabled Workspace.
    await service.update_settings(WS, {'enabled': True})
    yield SimpleNamespace(service=service, email=email, space=space, pusher=pusher, engine=engine)
    await engine.dispose()


async def _workspace(workspace_uuid):
    return SimpleNamespace(name='Support Team')


async def _drain(service: AlertService) -> None:
    while not service._queue.empty():
        await service._handle_signal(service._queue.get_nowait())


async def _incidents(engine):
    async with engine.connect() as connection:
        return (await connection.execute(sqlalchemy.select(alert_entity.AlertIncident))).all()


async def test_threshold_opens_one_incident_and_notifies_once(env):
    service = env.service
    for _ in range(4):
        service.observe_failure(WS, 'pipeline_failures', 'pipe-1', 'Default', error_type='E', error_message='boom')
    await _drain(service)
    assert await _incidents(env.engine) == []

    service.observe_failure(
        WS,
        'pipeline_failures',
        'pipe-1',
        'Default',
        error_type='RuntimeError',
        error_message='upstream failed api_key=sk-abcdefghijklmnop user@example.com',
    )
    await _drain(service)
    incidents = await _incidents(env.engine)
    assert len(incidents) == 1
    assert incidents[0].state == 'firing'
    assert 'sk-abcdefghijklmnop' not in incidents[0].error_summary
    assert 'user@example.com' not in incidents[0].error_summary

    await service.tick()
    # Owner + admin receive it; the viewer does not.
    assert sorted(item['to'][0] for item in env.email.sent) == ['admin@example.com', 'owner@example.com']
    assert 'Support Team' in env.email.sent[0]['subject']
    assert 'sk-abcdefghijklmnop' not in env.email.sent[0]['text']

    # More failures and more passes do not notify again.
    for _ in range(10):
        service.observe_failure(WS, 'pipeline_failures', 'pipe-1', 'Default')
    await _drain(service)
    await service.tick()
    assert len(env.email.sent) == 2
    assert len(await _incidents(env.engine)) == 1


async def test_reminder_backoff_and_quiet_auto_resolve(env):
    service = env.service
    for _ in range(5):
        service.observe_failure(WS, 'pipeline_failures', 'pipe-1', 'Default')
    await _drain(service)
    await service.tick()
    assert len(env.email.sent) == 2

    old = alert_module.utcnow() - datetime.timedelta(hours=7)
    async with env.engine.begin() as connection:
        await connection.execute(sqlalchemy.update(alert_entity.AlertIncident).values(last_notified_at=old))
    await service.tick()
    assert len(env.email.sent) == 4
    assert '[LangBot] Still failing' in env.email.sent[-1]['subject']
    await service.tick()
    assert len(env.email.sent) == 4  # next reminder waits 12h

    quiet = alert_module.utcnow() - datetime.timedelta(minutes=16)
    async with env.engine.begin() as connection:
        await connection.execute(sqlalchemy.update(alert_entity.AlertIncident).values(last_seen_at=quiet))
    await service.tick()
    assert [incident.state for incident in await _incidents(env.engine)] == ['resolved']
    assert '[LangBot] Resolved' in env.email.sent[-1]['subject']
    sent = len(env.email.sent)
    await service.tick()
    assert len(env.email.sent) == sent
    assert WS not in service._active_workspaces


async def test_bot_offline_fires_on_one_crash_and_resolves_on_restart(env):
    service = env.service
    service.observe_failure(WS, 'bot_offline', 'bot-1', 'QQ Bot', error_type='ConnectionError', error_message='x')
    await _drain(service)
    await service.tick()
    assert len(env.email.sent) == 2
    service.observe_recovery(WS, 'bot_offline', 'bot-1')
    await _drain(service)
    await service.tick()
    assert [incident.state for incident in await _incidents(env.engine)] == ['resolved']
    assert '[LangBot] Resolved' in env.email.sent[-1]['subject']


async def test_incident_resolved_before_first_notice_stays_silent(env, monkeypatch):
    monkeypatch.setattr(alert_module, 'FIRED_GRACE_SECONDS', 3600)
    service = env.service
    service.observe_failure(WS, 'bot_offline', 'bot-1', 'QQ Bot')
    await _drain(service)
    await service.tick()
    service.observe_recovery(WS, 'bot_offline', 'bot-1')
    await _drain(service)
    await service.tick()
    assert env.email.sent == []


async def test_space_channel_never_sends_recipients_or_free_text(env):
    service = env.service
    env.email.enabled = False
    await service.update_settings(WS, {'enabled': True, 'email_channel': 'auto', 'webhook_ids': [7]})
    service.observe_failure(WS, 'bot_offline', 'bot-1', 'QQ Bot', error_message='x' * 1000)
    await _drain(service)
    await service.tick()

    # Only the Space-linked admin is mailed, through their own token.
    assert len(env.space.calls) == 1
    token, payload = env.space.calls[0]
    assert token == 'token-for-admin@example.com'
    assert set(payload) == {
        'instance_id',
        'workspace_uuid',
        'workspace_name',
        'kind',
        'language',
        'incidents',
        'idempotency_key',
    }
    assert 'admin@example.com' not in str(payload)
    assert len(payload['incidents'][0]['error_summary']) <= 300
    assert env.email.sent == []
    # The selected webhook receives the structured event.
    assert env.pusher.events[0][1]['event_type'] == 'alert.fired'

    deliveries = await service.list_deliveries(WS)
    assert {(item['channel'], item['status']) for item in deliveries} == {('space', 'sent'), ('webhook', 'sent')}


async def test_space_quota_is_recorded_as_rate_limited(env):
    service = env.service
    env.email.enabled = False
    env.space.status = 429
    deliveries = await service.send_test(WS)
    assert [item['status'] for item in deliveries] == ['rate_limited']


async def test_settings_validation_mute_and_channel_choice(env):
    service = env.service
    with pytest.raises(ValueError):
        service.validate_settings({'email_channel': 'carrier-pigeon'})
    with pytest.raises(ValueError):
        service.validate_settings({'extra_recipients': ['not-an-email']})
    with pytest.raises(ValueError):
        service.validate_settings({'extra_recipients': [f'a{i}@example.com' for i in range(11)]})

    settings = await service.update_settings(
        WS,
        {
            'enabled': True,
            'email_channel': 'instance',
            'muted_account_uuids': [ADMIN],
            'extra_recipients': ['Oncall@Example.com'],
            'rules': {'pipeline_failures': {'threshold': 1, 'window_minutes': 999}, 'unknown': {}},
        },
    )
    # Thresholds and windows are clamped to the rule bounds.
    assert settings['rules']['pipeline_failures'] == {'enabled': True, 'threshold': 3, 'window_minutes': 60}
    assert 'unknown' not in settings['rules']

    await service.send_test(WS)
    assert sorted(item['to'][0] for item in env.email.sent) == ['oncall@example.com', 'owner@example.com']

    # Both channels available: the explicit choice decides.
    await service.update_settings(WS, {'enabled': True, 'email_channel': 'space'})
    await service.send_test(WS)
    assert len(env.space.calls) == 1
    await service.send_test(WS)  # third test within ten minutes is still allowed
    with pytest.raises(PermissionError):
        await service.send_test(WS)


async def test_daily_email_budget_caps_instance_mail(env, monkeypatch):
    monkeypatch.setattr(alert_module, 'MAX_EMAILS_PER_WORKSPACE_PER_DAY', 3)
    monkeypatch.setattr(alert_module, 'TEST_LIMIT', 10)
    service = env.service
    await service.send_test(WS)
    deliveries = await service.send_test(WS)
    assert [item['status'] for item in deliveries] == ['sent', 'rate_limited']


async def test_disabled_rule_and_instance_switch_ignore_failures(env):
    service = env.service
    await service.update_settings(WS, {'enabled': True, 'rules': {'model_failures': {'enabled': False}}})
    for _ in range(20):
        service.observe_failure(WS, 'model_failures', 'gpt', 'gpt')
    await _drain(service)
    assert await _incidents(env.engine) == []

    service.ap.instance_config.data['alerts']['enabled'] = False
    service.observe_failure(WS, 'bot_offline', 'bot-1', 'Bot')
    assert service._queue.empty()


async def test_alerts_are_off_until_a_workspace_opts_in(env):
    service = env.service
    async with env.engine.begin() as connection:
        await connection.execute(sqlalchemy.delete(alert_entity.AlertSetting))
    service._settings_cache.clear()

    summary = await service.summary(WS)
    assert summary == {'enabled_instance_wide': True, 'enabled': False, 'firing': 0}
    for _ in range(10):
        service.observe_failure(WS, 'bot_offline', 'bot-1', 'Bot')
    await _drain(service)
    assert await _incidents(env.engine) == []

    # Saving settings without an explicit flag keeps alerts off.
    assert (await service.update_settings(WS, {'email_channel': 'auto'}))['enabled'] is False
    await service.update_settings(WS, {'enabled': True})
    service.observe_failure(WS, 'bot_offline', 'bot-1', 'Bot')
    await _drain(service)
    assert (await service.summary(WS))['firing'] == 1
    state = await service.channel_state(WS)
    assert state['space']['supported'] is True


async def test_cloud_workspaces_default_to_alerts_on(env):
    service = env.service
    async with env.engine.begin() as connection:
        await connection.execute(sqlalchemy.delete(alert_entity.AlertSetting))
    service._settings_cache.clear()
    service.ap.deployment = SimpleNamespace(mode='cloud')

    assert (await service.summary(WS))['enabled'] is True
    service.observe_failure(WS, 'bot_offline', 'bot-1', 'Bot')
    await _drain(service)
    assert (await service.summary(WS))['firing'] == 1

    # An explicit choice still wins over the Cloud default.
    await service.update_settings(WS, {'enabled': False})
    assert (await service.summary(WS))['enabled'] is False
