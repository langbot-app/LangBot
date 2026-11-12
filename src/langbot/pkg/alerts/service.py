"""Workspace failure alerts.

Producers (monitoring writes, platform adapters) call :meth:`observe_failure`
and :meth:`observe_recovery`. Both are synchronous and only enqueue a signal,
so the hot path never waits on alert storage or delivery. One worker task per
process drains the queue, keeps sliding windows in memory, opens incidents in
the database and runs a periodic pass that auto-resolves quiet incidents and
delivers notifications.

Delivery is claimed per incident with compare-and-set updates, so replicas
sharing one database never notify twice. Alert delivery failures are logged
and recorded, never turned into new alerts.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import datetime
import hashlib
import re
import time
import typing
import uuid

import sqlalchemy

from ..entity.persistence import alert as alert_entity
from ..entity.persistence.user import AccountStatus, User
from ..entity.persistence.webhook import Webhook
from ..entity.persistence.workspace import MembershipStatus, WorkspaceMembership
from ..notification.email import EmailService
from ..telemetry.execution import redact_text
from . import render, rules

if typing.TYPE_CHECKING:
    from ..core.app import Application


EMAIL_CHANNELS = ('auto', 'instance', 'space', 'off')
RECIPIENT_ROLES = ('owner', 'admin')
MAX_EXTRA_RECIPIENTS = 10
MAX_EMAILS_PER_WORKSPACE_PER_DAY = 50
DELIVERY_HISTORY_LIMIT = 200
TEST_LIMIT = 3
TEST_WINDOW_SECONDS = 600
FIRED_GRACE_SECONDS = 20  # group incidents that open together into one message
TOUCH_INTERVAL_SECONDS = 30
SETTINGS_CACHE_SECONDS = 30
QUEUE_SIZE = 10000
MAX_WINDOW_KEYS = 20000
SUMMARY_LIMIT = 300
_EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{1,63}$')


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def mask_email(address: str) -> str:
    local, _, domain = address.partition('@')
    if not domain:
        return '***'
    return f'{local[:1]}***@{domain}'


def summarize_error(error_type: str | None, error_message: str | None) -> tuple[str | None, str | None]:
    error_type = str(error_type or '').strip()[:128] or None
    message = ' '.join(str(error_message or '').split())
    if not message:
        return error_type, None
    message = redact_text(message)
    if len(message) > SUMMARY_LIMIT:
        message = message[: SUMMARY_LIMIT - 1] + '…'
    return error_type, message


class _Signal(typing.NamedTuple):
    kind: str  # failure | recovery
    workspace_uuid: str
    rule: str
    subject_id: str
    subject_name: str
    error_type: str | None
    error_message: str | None
    at: float


class AlertService:
    def __init__(self, ap: Application) -> None:
        self.ap = ap
        self._queue: asyncio.Queue[_Signal] | None = None
        self._windows: collections.OrderedDict[tuple[str, str, str], collections.deque[float]] = (
            collections.OrderedDict()
        )
        # (workspace, fingerprint) -> (incident id, last DB touch monotonic time)
        self._firing: dict[tuple[str, str], tuple[str, float]] = {}
        self._active_workspaces: set[str] = set()
        self._settings_cache: dict[str, tuple[dict, float]] = {}
        self._tests: dict[str, collections.deque[float]] = {}
        self._email = EmailService(ap)

    # ------------------------------------------------------------------ config

    def _config(self) -> dict:
        data = getattr(getattr(self.ap, 'instance_config', None), 'data', {}) or {}
        section = data.get('alerts')
        return section if isinstance(section, dict) else {}

    def enabled(self) -> bool:
        return bool(self._config().get('enabled', True))

    def _tick_seconds(self) -> float:
        try:
            return min(max(float(self._config().get('tick_seconds', 30)), 5.0), 600.0)
        except (TypeError, ValueError):
            return 30.0

    def _email_service(self) -> EmailService:
        return getattr(self.ap, 'email_service', None) or self._email

    # --------------------------------------------------------------- producers

    def observe_failure(
        self,
        workspace_uuid: str | None,
        rule: str,
        subject_id: str | None,
        subject_name: str | None = None,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self._enqueue('failure', workspace_uuid, rule, subject_id, subject_name, error_type, error_message)

    def observe_recovery(self, workspace_uuid: str | None, rule: str, subject_id: str | None) -> None:
        self._enqueue('recovery', workspace_uuid, rule, subject_id, None, None, None)

    def _enqueue(self, kind, workspace_uuid, rule, subject_id, subject_name, error_type, error_message) -> None:
        if self._queue is None or not workspace_uuid or not subject_id or rule not in rules.RULES:
            return
        if not self.enabled():
            return
        signal = _Signal(
            kind,
            str(workspace_uuid),
            rule,
            str(subject_id)[:255],
            str(subject_name or subject_id)[:255],
            error_type,
            str(error_message)[:2000] if error_message else None,
            time.monotonic(),
        )
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(signal)

    # ------------------------------------------------------------------ worker

    async def run(self) -> None:
        """Drain signals and run the periodic delivery pass until cancelled."""

        self._queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        await self._restore_active_workspaces()
        loop = asyncio.get_running_loop()
        next_tick = loop.time() + self._tick_seconds()
        while True:
            timeout = max(next_tick - loop.time(), 0.0)
            try:
                signal = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                signal = None
            if signal is not None:
                try:
                    await self._handle_signal(signal)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._warn(f'Alert signal handling failed: {exc.__class__.__name__}: {exc}')
            if loop.time() >= next_tick:
                if self.enabled():
                    await self.tick()
                next_tick = loop.time() + self._tick_seconds()

    async def _restore_active_workspaces(self) -> None:
        """Pick up firing incidents left by a previous process."""

        workspace_service = getattr(self.ap, 'workspace_service', None)
        if workspace_service is None:
            return
        try:
            bindings = await workspace_service.list_active_execution_bindings()
        except Exception as exc:
            self._warn(f'Alert startup Workspace discovery failed: {exc}')
            return
        for binding in bindings:
            try:
                async with self._scope(binding.workspace_uuid):
                    rows = (
                        await self.ap.persistence_mgr.execute_async(
                            sqlalchemy.select(
                                alert_entity.AlertIncident.id, alert_entity.AlertIncident.fingerprint
                            ).where(
                                alert_entity.AlertIncident.workspace_uuid == binding.workspace_uuid,
                                sqlalchemy.or_(
                                    alert_entity.AlertIncident.state == alert_entity.INCIDENT_FIRING,
                                    sqlalchemy.and_(
                                        alert_entity.AlertIncident.notified_at.is_not(None),
                                        alert_entity.AlertIncident.resolved_notified_at.is_(None),
                                    ),
                                ),
                            )
                        )
                    ).all()
            except Exception as exc:
                self._warn(f'Alert startup scan failed for Workspace {binding.workspace_uuid}: {exc}')
                continue
            if rows:
                self._active_workspaces.add(binding.workspace_uuid)

    @contextlib.asynccontextmanager
    async def _scope(self, workspace_uuid: str):
        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(workspace_uuid):
                yield
        else:
            yield

    async def _execute(self, workspace_uuid: str, statement):
        async with self._scope(workspace_uuid):
            return await self.ap.persistence_mgr.execute_async(statement)

    async def _handle_signal(self, signal: _Signal) -> None:
        settings = await self._settings(signal.workspace_uuid)
        rule_cfg = settings['rules'].get(signal.rule, {})
        fingerprint = f'{signal.rule}:{signal.subject_id}'
        firing_key = (signal.workspace_uuid, fingerprint)

        if signal.kind == 'recovery':
            self._windows.pop((signal.workspace_uuid, signal.rule, signal.subject_id), None)
            if firing_key in self._firing or signal.workspace_uuid in self._active_workspaces:
                await self._resolve(signal.workspace_uuid, fingerprint)
            return

        if not settings['enabled'] or not rule_cfg.get('enabled', True):
            return

        window_key = (signal.workspace_uuid, signal.rule, signal.subject_id)
        window = self._windows.pop(window_key, None) or collections.deque()
        window.append(signal.at)
        horizon = signal.at - rule_cfg['window_minutes'] * 60
        while window and window[0] < horizon:
            window.popleft()
        self._windows[window_key] = window
        while len(self._windows) > MAX_WINDOW_KEYS:
            self._windows.popitem(last=False)

        if len(window) < rule_cfg['threshold'] and firing_key not in self._firing:
            return
        error_type, summary = summarize_error(signal.error_type, signal.error_message)
        await self._open_or_touch(signal, fingerprint, len(window), error_type, summary)

    async def _open_or_touch(self, signal, fingerprint, count, error_type, summary) -> None:
        Incident = alert_entity.AlertIncident
        workspace_uuid = signal.workspace_uuid
        firing_key = (workspace_uuid, fingerprint)
        now = utcnow()
        known = self._firing.get(firing_key)
        if known is not None:
            incident_id, touched = known
            if signal.at - touched < TOUCH_INTERVAL_SECONDS:
                return
            result = await self._execute(
                workspace_uuid,
                sqlalchemy.update(Incident)
                .where(Incident.id == incident_id, Incident.state == alert_entity.INCIDENT_FIRING)
                .values(
                    last_seen_at=now,
                    event_count=Incident.event_count + count,
                    error_type=error_type or Incident.error_type,
                    error_summary=summary or Incident.error_summary,
                ),
            )
            if (result.rowcount or 0) > 0:
                self._firing[firing_key] = (incident_id, signal.at)
                self._windows.pop((workspace_uuid, signal.rule, signal.subject_id), None)
                return
            # Resolved meanwhile (another replica or a recovery): open anew.
            self._firing.pop(firing_key, None)

        existing = (
            await self._execute(
                workspace_uuid,
                sqlalchemy.select(Incident.id).where(
                    Incident.workspace_uuid == workspace_uuid,
                    Incident.fingerprint == fingerprint,
                    Incident.state == alert_entity.INCIDENT_FIRING,
                ),
            )
        ).first()
        if existing is not None:
            self._firing[firing_key] = (existing[0], 0.0)
            await self._open_or_touch(signal, fingerprint, count, error_type, summary)
            return

        incident_id = str(uuid.uuid4())
        try:
            await self._execute(
                workspace_uuid,
                sqlalchemy.insert(Incident).values(
                    id=incident_id,
                    workspace_uuid=workspace_uuid,
                    rule=signal.rule,
                    fingerprint=fingerprint,
                    subject_id=signal.subject_id,
                    subject_name=signal.subject_name,
                    state=alert_entity.INCIDENT_FIRING,
                    event_count=count,
                    error_type=error_type,
                    error_summary=summary,
                    opened_at=now,
                    last_seen_at=now,
                    reminder_count=0,
                ),
            )
        except sqlalchemy.exc.IntegrityError:
            # Another replica opened it first; adopt that incident next time.
            return
        self._firing[firing_key] = (incident_id, signal.at)
        self._windows.pop((workspace_uuid, signal.rule, signal.subject_id), None)
        self._active_workspaces.add(workspace_uuid)

    async def _resolve(self, workspace_uuid: str, fingerprint: str) -> None:
        Incident = alert_entity.AlertIncident
        await self._execute(
            workspace_uuid,
            sqlalchemy.update(Incident)
            .where(
                Incident.workspace_uuid == workspace_uuid,
                Incident.fingerprint == fingerprint,
                Incident.state == alert_entity.INCIDENT_FIRING,
            )
            .values(state=alert_entity.INCIDENT_RESOLVED, resolved_at=utcnow()),
        )
        self._firing.pop((workspace_uuid, fingerprint), None)

    # ------------------------------------------------------------ periodic pass

    async def tick(self) -> None:
        for workspace_uuid in list(self._active_workspaces):
            try:
                still_active = await self._tick_workspace(workspace_uuid)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._warn(f'Alert pass failed for Workspace {workspace_uuid}: {exc.__class__.__name__}: {exc}')
                continue
            if not still_active:
                self._active_workspaces.discard(workspace_uuid)

    async def _tick_workspace(self, workspace_uuid: str) -> bool:
        Incident = alert_entity.AlertIncident
        now = utcnow()

        # Auto-resolve incidents that stayed quiet.
        for name, spec in rules.RULES.items():
            if spec.quiet_minutes is None:
                continue
            await self._execute(
                workspace_uuid,
                sqlalchemy.update(Incident)
                .where(
                    Incident.workspace_uuid == workspace_uuid,
                    Incident.rule == name,
                    Incident.state == alert_entity.INCIDENT_FIRING,
                    Incident.last_seen_at < now - datetime.timedelta(minutes=spec.quiet_minutes),
                )
                .values(state=alert_entity.INCIDENT_RESOLVED, resolved_at=now),
            )

        rows = (
            await self._execute(
                workspace_uuid,
                sqlalchemy.select(Incident).where(
                    Incident.workspace_uuid == workspace_uuid,
                    sqlalchemy.or_(
                        Incident.state == alert_entity.INCIDENT_FIRING,
                        Incident.resolved_notified_at.is_(None),
                    ),
                ),
            )
        ).all()
        # execute_async keeps the Core-result contract: rows expose columns.
        incidents = list(rows)

        firing_keys = {
            (workspace_uuid, item.fingerprint) for item in incidents if item.state == alert_entity.INCIDENT_FIRING
        }
        for key in [key for key in self._firing if key[0] == workspace_uuid and key not in firing_keys]:
            self._firing.pop(key, None)

        fired, reminders, resolved = [], [], []
        for item in incidents:
            if item.state == alert_entity.INCIDENT_FIRING:
                if item.notified_at is None:
                    if item.opened_at <= now - datetime.timedelta(seconds=FIRED_GRACE_SECONDS):
                        if await self._claim(
                            workspace_uuid,
                            Incident.id == item.id,
                            Incident.notified_at.is_(None),
                            values={'notified_at': now, 'last_notified_at': now},
                        ):
                            fired.append(item)
                else:
                    due = (item.last_notified_at or item.notified_at) + datetime.timedelta(
                        hours=rules.reminder_interval_hours(item.reminder_count)
                    )
                    if due <= now and await self._claim(
                        workspace_uuid,
                        Incident.id == item.id,
                        Incident.last_notified_at == item.last_notified_at,
                        values={'last_notified_at': now, 'reminder_count': item.reminder_count + 1},
                    ):
                        reminders.append(item)
            elif item.resolved_notified_at is None:
                if await self._claim(
                    workspace_uuid,
                    Incident.id == item.id,
                    Incident.resolved_notified_at.is_(None),
                    values={'resolved_notified_at': now},
                ):
                    # Incidents resolved before their first notice stay silent.
                    if item.notified_at is not None:
                        resolved.append(item)

        settings = await self._settings(workspace_uuid)
        for kind, batch in (('fired', fired), ('reminder', reminders), ('resolved', resolved)):
            if not batch or (kind == 'resolved' and not settings['notify_resolved']):
                continue
            if not settings['enabled']:
                continue
            await self.dispatch(workspace_uuid, kind, [self._incident_payload(item) for item in batch])

        # Resolved incidents were all claimed above; only firing ones need more passes.
        return bool(firing_keys)

    async def _claim(self, workspace_uuid: str, *conditions, values: dict) -> bool:
        result = await self._execute(
            workspace_uuid,
            sqlalchemy.update(alert_entity.AlertIncident).where(*conditions).values(**values),
        )
        return (result.rowcount or 0) > 0

    @staticmethod
    def _incident_payload(item) -> dict[str, typing.Any]:
        return {
            'id': item.id,
            'rule': item.rule,
            'subject_id': item.subject_id,
            'subject_name': item.subject_name,
            'state': item.state,
            'event_count': int(item.event_count or 0),
            'error_type': item.error_type,
            'error_summary': item.error_summary,
            'opened_at': item.opened_at.isoformat(),
            'last_seen_at': item.last_seen_at.isoformat() if item.last_seen_at else None,
            'resolved_at': item.resolved_at.isoformat() if item.resolved_at else None,
        }

    # ---------------------------------------------------------------- settings

    async def _settings(self, workspace_uuid: str, *, refresh: bool = False) -> dict:
        cached = self._settings_cache.get(workspace_uuid)
        if cached is not None and not refresh and time.monotonic() - cached[1] < SETTINGS_CACHE_SECONDS:
            return cached[0]
        row = (
            await self._execute(
                workspace_uuid,
                sqlalchemy.select(alert_entity.AlertSetting).where(
                    alert_entity.AlertSetting.workspace_uuid == workspace_uuid
                ),
            )
        ).first()
        settings = self._normalize_settings(row)
        self._settings_cache[workspace_uuid] = (settings, time.monotonic())
        if len(self._settings_cache) > MAX_WINDOW_KEYS:
            self._settings_cache.pop(next(iter(self._settings_cache)))
        return settings

    def default_enabled(self) -> bool:
        """Whether a Workspace without saved settings has alerts on.

        Multi-tenant Cloud turns alerts on for every Workspace (existing and
        new) and mails through the platform-configured service. Self-hosted and
        dedicated instances are opt-in: nothing is evaluated or sent until an
        admin turns alerts on. A saved choice always wins.
        """

        return getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'cloud'

    def _normalize_settings(self, setting) -> dict:
        if setting is None:
            return {
                'enabled': self.default_enabled(),
                'email_channel': 'auto',
                'rules': rules.normalize_rules({}),
                'webhook_ids': [],
                'extra_recipients': [],
                'muted_account_uuids': [],
                'notify_resolved': True,
            }
        return {
            'enabled': bool(setting.enabled),
            'email_channel': setting.email_channel if setting.email_channel in EMAIL_CHANNELS else 'auto',
            'rules': rules.normalize_rules(setting.rules),
            'webhook_ids': [int(item) for item in (setting.webhook_ids or []) if str(item).isdigit()],
            'extra_recipients': [str(item) for item in (setting.extra_recipients or [])][:MAX_EXTRA_RECIPIENTS],
            'muted_account_uuids': [str(item) for item in (setting.muted_account_uuids or [])],
            'notify_resolved': bool(setting.notify_resolved),
        }

    def validate_settings(self, payload: dict) -> dict:
        """Validate a settings update; raises ValueError with a stable message."""

        if not isinstance(payload, dict):
            raise ValueError('Invalid alert settings')
        email_channel = payload.get('email_channel', 'auto')
        if email_channel not in EMAIL_CHANNELS:
            raise ValueError('email_channel must be one of auto, instance, space, off')
        extra = payload.get('extra_recipients') or []
        if not isinstance(extra, list) or len(extra) > MAX_EXTRA_RECIPIENTS:
            raise ValueError(f'At most {MAX_EXTRA_RECIPIENTS} extra recipients are allowed')
        normalized_extra = []
        for address in extra:
            address = str(address).strip().lower()
            if not _EMAIL_RE.match(address):
                raise ValueError(f'Invalid email address: {address[:80]}')
            if address not in normalized_extra:
                normalized_extra.append(address)
        webhook_ids = payload.get('webhook_ids') or []
        if not isinstance(webhook_ids, list) or not all(str(item).isdigit() for item in webhook_ids):
            raise ValueError('webhook_ids must be a list of webhook IDs')
        muted = payload.get('muted_account_uuids') or []
        if not isinstance(muted, list):
            raise ValueError('muted_account_uuids must be a list')
        return {
            'enabled': bool(payload.get('enabled', self.default_enabled())),
            'email_channel': email_channel,
            'rules': rules.normalize_rules(payload.get('rules')),
            'webhook_ids': sorted({int(item) for item in webhook_ids}),
            'extra_recipients': normalized_extra,
            'muted_account_uuids': sorted({str(item)[:36] for item in muted})[:100],
            'notify_resolved': bool(payload.get('notify_resolved', True)),
        }

    async def update_settings(self, workspace_uuid: str, payload: dict) -> dict:
        values = self.validate_settings(payload)
        Setting = alert_entity.AlertSetting
        async with self._scope(workspace_uuid):
            existing = (
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(Setting.workspace_uuid).where(Setting.workspace_uuid == workspace_uuid)
                )
            ).first()
            if existing is None:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(Setting).values(workspace_uuid=workspace_uuid, **values)
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(Setting).where(Setting.workspace_uuid == workspace_uuid).values(**values)
                )
        return await self._settings(workspace_uuid, refresh=True)

    async def recipients(self, workspace_uuid: str) -> list[dict[str, typing.Any]]:
        rows = (
            await self._execute(
                workspace_uuid,
                sqlalchemy.select(
                    WorkspaceMembership.account_uuid,
                    WorkspaceMembership.role,
                    User.user,
                    User.normalized_email,
                    User.account_type,
                    User.space_refresh_token,
                    User.space_access_token,
                )
                .join(User, User.uuid == WorkspaceMembership.account_uuid)
                .where(
                    WorkspaceMembership.workspace_uuid == workspace_uuid,
                    WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
                    WorkspaceMembership.role.in_(RECIPIENT_ROLES),
                    User.status == AccountStatus.ACTIVE.value,
                )
                .order_by(WorkspaceMembership.created_at),
            )
        ).all()
        return [
            {
                'account_uuid': account_uuid,
                'role': role,
                'login': login,
                'email': email,
                'space_linked': account_type == 'space' and bool(refresh_token or access_token),
            }
            for account_uuid, role, login, email, account_type, refresh_token, access_token in rows
            if email and _EMAIL_RE.match(email)
        ]

    def _space_available(self) -> bool:
        if getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'cloud':
            # Multi-tenant Cloud mails through the platform-configured service.
            return False
        return getattr(self.ap, 'space_service', None) is not None

    async def channel_state(self, workspace_uuid: str, settings: dict | None = None) -> dict[str, typing.Any]:
        settings = settings or await self._settings(workspace_uuid)
        recipients = await self.recipients(workspace_uuid)
        muted = set(settings['muted_account_uuids'])
        active = [item for item in recipients if item['account_uuid'] not in muted]
        instance = self._email_service().capability()
        space_accounts = [item for item in active if item['space_linked']] if self._space_available() else []
        effective = self._effective_channel(settings['email_channel'], instance['enabled'], bool(space_accounts))
        return {
            'instance': {'configured': bool(instance['enabled']), 'provider': instance['provider']},
            'space': {
                'supported': self._space_available(),
                'available': bool(space_accounts),
                'accounts': [mask_email(item['email']) for item in space_accounts],
            },
            'effective_email_channel': effective,
            'recipients': recipients,
        }

    @staticmethod
    def _effective_channel(choice: str, instance_ok: bool, space_ok: bool) -> str | None:
        if choice == 'off':
            return None
        if choice == 'instance':
            return 'instance' if instance_ok else None
        if choice == 'space':
            return 'space' if space_ok else None
        if instance_ok:
            return 'instance'
        return 'space' if space_ok else None

    # ---------------------------------------------------------------- delivery

    async def dispatch(self, workspace_uuid: str, kind: str, incidents: list[dict]) -> list[dict]:
        """Notify every configured channel; returns the recorded delivery rows."""

        settings = await self._settings(workspace_uuid)
        state = await self.channel_state(workspace_uuid, settings)
        workspace_name, language = await self._workspace_identity(workspace_uuid)
        deliveries: list[dict] = []

        channel = state['effective_email_channel']
        muted = set(settings['muted_account_uuids'])
        recipients = [item for item in state['recipients'] if item['account_uuid'] not in muted]
        if channel == 'instance':
            addresses = [item['email'] for item in recipients] + settings['extra_recipients']
            addresses = list(dict.fromkeys(addresses))
            budget = await self._email_budget(workspace_uuid)
            subject, text, html = render.render_alert_email(
                kind=kind,
                workspace_name=workspace_name,
                incidents=incidents,
                message_language=language,
                console_url=self._console_url(),
            )
            for address in addresses:
                if budget <= 0:
                    deliveries.append(self._delivery(kind, 'email', mask_email(address), 'rate_limited', None))
                    continue
                budget -= 1
                result = await self._email_service().send(
                    to=[address], subject=subject, text=text, html=html, purpose='Alert email'
                )
                deliveries.append(
                    self._delivery(
                        kind,
                        'email',
                        mask_email(address),
                        'sent' if result.status == 'sent' else 'failed',
                        result.error,
                    )
                )
        elif channel == 'space':
            payload = self._space_payload(workspace_uuid, workspace_name, language, kind, incidents)
            for item in recipients:
                if not item['space_linked']:
                    continue
                deliveries.append(await self._send_via_space(kind, item, payload))

        if settings['webhook_ids']:
            deliveries.extend(await self._send_webhooks(workspace_uuid, workspace_name, kind, settings, incidents))

        if deliveries:
            await self._record_deliveries(workspace_uuid, deliveries, len(incidents))
        return deliveries

    @staticmethod
    def _delivery(kind: str, channel: str, target: str, status: str, error: str | None) -> dict:
        return {
            'kind': kind,
            'channel': channel,
            'target': target[:255],
            'status': status,
            'error': (error or None) and str(error)[:255],
        }

    async def _email_budget(self, workspace_uuid: str) -> int:
        Delivery = alert_entity.AlertDelivery
        since = utcnow() - datetime.timedelta(days=1)
        sent = (
            await self._execute(
                workspace_uuid,
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(Delivery)
                .where(
                    Delivery.workspace_uuid == workspace_uuid,
                    Delivery.channel == 'email',
                    Delivery.status == 'sent',
                    Delivery.created_at >= since,
                ),
            )
        ).scalar() or 0
        return max(MAX_EMAILS_PER_WORKSPACE_PER_DAY - int(sent), 0)

    def _space_payload(self, workspace_uuid, workspace_name, language, kind, incidents) -> dict:
        from ..utils import constants

        # Space deduplicates on this key, so a retried request never mails twice.
        stamp = {'reminder': utcnow().strftime('%Y%m%d%H'), 'test': str(uuid.uuid4())}.get(kind, '')
        key_material = f'{workspace_uuid}:{kind}:{",".join(sorted(item["id"] for item in incidents))}:{stamp}'
        return {
            'instance_id': str(getattr(constants, 'instance_id', '') or ''),
            'workspace_uuid': workspace_uuid,
            'workspace_name': workspace_name[:64],
            'kind': kind,
            'language': render.text_language(language),
            'incidents': [
                {
                    'rule': item['rule'],
                    'subject_name': str(item['subject_name'])[:64],
                    'count': int(item['event_count']),
                    'error_type': (item.get('error_type') or '')[:64],
                    'error_summary': (item.get('error_summary') or '')[:SUMMARY_LIMIT],
                    'opened_at': item['opened_at'][:19] + 'Z',
                }
                for item in incidents[:10]
            ],
            'idempotency_key': hashlib.sha256(key_material.encode()).hexdigest(),
        }

    async def _send_via_space(self, kind: str, recipient: dict, payload: dict) -> dict:
        target = mask_email(recipient['email'])
        space_service = getattr(self.ap, 'space_service', None)
        try:
            token = await space_service.get_valid_access_token(recipient['login'])
        except Exception:
            token = None
        if not token:
            return self._delivery(kind, 'space', target, 'failed', 'space_token_unavailable')
        try:
            status, data = await space_service.send_alert_email(token, payload)
        except Exception as exc:
            return self._delivery(kind, 'space', target, 'failed', f'space_unreachable: {exc.__class__.__name__}')
        if 200 <= status < 300:
            return self._delivery(kind, 'space', target, 'sent', None)
        if status == 429:
            return self._delivery(kind, 'space', target, 'rate_limited', data.get('msg') or 'space_quota_exceeded')
        if status == 404:
            return self._delivery(kind, 'space', target, 'failed', 'space_endpoint_unavailable')
        return self._delivery(kind, 'space', target, 'failed', f'space_http_{status}: {data.get("msg", "")}')

    async def _send_webhooks(self, workspace_uuid, workspace_name, kind, settings, incidents) -> list[dict]:
        wanted = set(settings['webhook_ids'])
        rows = (
            await self._execute(
                workspace_uuid,
                sqlalchemy.select(Webhook.id, Webhook.name, Webhook.url).where(
                    Webhook.workspace_uuid == workspace_uuid,
                    Webhook.enabled == True,  # noqa: E712
                    Webhook.id.in_(wanted),
                ),
            )
        ).all()
        if not rows:
            return []
        payload = {
            'uuid': str(uuid.uuid4()),
            'event_type': f'alert.{kind}',
            'data': {
                'workspace_uuid': workspace_uuid,
                'workspace_name': workspace_name,
                'incidents': incidents,
            },
        }
        pusher = getattr(self.ap, 'webhook_pusher', None)
        if pusher is None:
            return []
        results = await pusher.deliver_event([{'url': url} for _, _, url in rows], payload)
        return [
            self._delivery(kind, 'webhook', name, 'sent' if ok else 'failed', None if ok else 'webhook_failed')
            for (_, name, _), ok in zip(rows, results)
        ]

    async def _record_deliveries(self, workspace_uuid: str, deliveries: list[dict], incident_count: int) -> None:
        Delivery = alert_entity.AlertDelivery
        now = utcnow()
        async with self._scope(workspace_uuid):
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(Delivery),
                [
                    {**item, 'workspace_uuid': workspace_uuid, 'incident_count': incident_count, 'created_at': now}
                    for item in deliveries
                ],
            )
            cutoff = (
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(Delivery.id)
                    .where(Delivery.workspace_uuid == workspace_uuid)
                    .order_by(Delivery.id.desc())
                    .offset(DELIVERY_HISTORY_LIMIT)
                    .limit(1)
                )
            ).first()
            if cutoff is not None:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.delete(Delivery).where(
                        Delivery.workspace_uuid == workspace_uuid, Delivery.id <= cutoff[0]
                    )
                )

    async def _workspace_identity(self, workspace_uuid: str) -> tuple[str, str]:
        name = 'Workspace'
        try:
            workspace = await self.ap.workspace_service.get_workspace(workspace_uuid)
            name = str(getattr(workspace, 'name', '') or name)
        except Exception:
            pass
        language = 'en_US'
        try:
            from ..i18n.workspace import get_workspace_language

            language = await get_workspace_language(self.ap, workspace_uuid)
        except Exception:
            pass
        return name, language

    def _console_url(self) -> str | None:
        try:
            from ..workspace.invitation_delivery import InvitationDeliveryService

            url = InvitationDeliveryService(self.ap)._public_web_url().rstrip('/')
        except Exception:
            return None
        if url.startswith('http://127.0.0.1') or url.startswith('http://localhost'):
            return None
        return url

    # ------------------------------------------------------------------ reads

    async def list_incidents(self, workspace_uuid: str, *, state: str | None, limit: int = 50) -> list[dict]:
        Incident = alert_entity.AlertIncident
        statement = sqlalchemy.select(Incident).where(Incident.workspace_uuid == workspace_uuid)
        if state in (alert_entity.INCIDENT_FIRING, alert_entity.INCIDENT_RESOLVED):
            statement = statement.where(Incident.state == state)
        statement = statement.order_by(Incident.opened_at.desc()).limit(min(max(limit, 1), 200))
        rows = (await self._execute(workspace_uuid, statement)).all()
        return [self._incident_payload(row) for row in rows]

    async def summary(self, workspace_uuid: str) -> dict[str, typing.Any]:
        """Cheap status for the dashboard: whether alerts are on and how many fire."""

        settings = await self._settings(workspace_uuid)
        Incident = alert_entity.AlertIncident
        firing = (
            await self._execute(
                workspace_uuid,
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(Incident)
                .where(Incident.workspace_uuid == workspace_uuid, Incident.state == alert_entity.INCIDENT_FIRING),
            )
        ).scalar() or 0
        return {
            'enabled_instance_wide': self.enabled(),
            'enabled': bool(settings['enabled']),
            'firing': int(firing),
        }

    async def list_deliveries(self, workspace_uuid: str, *, limit: int = 50) -> list[dict]:
        Delivery = alert_entity.AlertDelivery
        rows = (
            await self._execute(
                workspace_uuid,
                sqlalchemy.select(Delivery)
                .where(Delivery.workspace_uuid == workspace_uuid)
                .order_by(Delivery.id.desc())
                .limit(min(max(limit, 1), DELIVERY_HISTORY_LIMIT)),
            )
        ).all()
        result = []
        for item in rows:
            result.append(
                {
                    'id': item.id,
                    'kind': item.kind,
                    'channel': item.channel,
                    'target': item.target,
                    'status': item.status,
                    'error': item.error,
                    'incident_count': item.incident_count,
                    'created_at': item.created_at.isoformat() if item.created_at else None,
                }
            )
        return result

    async def send_test(self, workspace_uuid: str) -> list[dict]:
        window = self._tests.setdefault(workspace_uuid, collections.deque())
        now = time.monotonic()
        while window and window[0] < now - TEST_WINDOW_SECONDS:
            window.popleft()
        if len(window) >= TEST_LIMIT:
            raise PermissionError('Too many test alerts; try again in a few minutes')
        window.append(now)
        sample = {
            'id': 'test',
            'rule': 'pipeline_failures',
            'subject_id': 'test',
            'subject_name': 'Example Pipeline',
            'state': 'firing',
            'event_count': 5,
            'error_type': 'TestAlert',
            'error_summary': 'This is a test alert. No action is needed.',
            'opened_at': utcnow().isoformat(),
            'last_seen_at': None,
            'resolved_at': None,
        }
        return await self.dispatch(workspace_uuid, 'test', [sample])

    def _warn(self, message: str) -> None:
        logger = getattr(self.ap, 'logger', None)
        if logger is not None:
            logger.warning(message)
