"""Email the Workspace owner once per UTC day when daily message usage nears the quota.

Called from the message reservation path only on Cloud. The check is a plain
integer comparison; a Workspace crossing the threshold claims the day's usage
row with a compare-and-set, so replicas sharing one database send one email.
Delivery runs in a background task and never affects message handling.
"""

from __future__ import annotations

import asyncio
import datetime
import html
import math
import re

import sqlalchemy as sa

from ..alerts import render
from ..entity.persistence.user import AccountStatus, User
from ..entity.persistence.workspace import MembershipStatus, WorkspaceMembership
from ..entity.persistence.workspace import WorkspaceMessageUsageDaily as Usage
from ..notification.email import EmailService

WARNING_RATIO = 0.8
_EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{1,63}$')
_tasks: set[asyncio.Task] = set()
# (workspace, day) pairs this process already settled, to skip the claim query.
_settled: set[tuple[str, datetime.date]] = set()

_TEXT = {
    'en': {
        'subject': "[LangBot] {workspace} has used {percent}% of today's messages ({used}/{limit})",
        'heading': 'Daily message quota almost used up',
        'intro': (
            'Workspace “{workspace}” has handled {used} messages today, {percent}% of its daily quota. '
            'Once the quota is used up, bots stop replying until it resets.'
        ),
        'rows': (
            ('Used today', '{used} / {limit} messages'),
            ('Remaining', '{remaining} messages'),
            ('Resets at', '{reset_utc} UTC'),
        ),
        'hint': 'Need more messages? Upgrade your plan to raise or remove the daily limit.',
        'open': 'View plans',
        'footer': 'Sent by LangBot Cloud because you own this Workspace. At most one reminder per Workspace per day.',
    },
    'zh': {
        'subject': '[LangBot] 「{workspace}」今日消息已用 {percent}%（{used}/{limit}）',
        'heading': '今日消息额度即将用完',
        'intro': (
            '工作区「{workspace}」今天已处理 {used} 条消息，达到每日额度的 {percent}%。'
            '用完后，机器人将暂停回复，直到额度重置。'
        ),
        'rows': (
            ('今日已用', '{used} / {limit} 条'),
            ('剩余', '{remaining} 条'),
            ('重置时间', '{reset_utc} UTC（北京时间 {reset_cst}）'),
        ),
        'hint': '需要更多消息？升级套餐即可提高或取消每日上限。',
        'open': '查看套餐',
        'footer': '由 LangBot Cloud 发送。你是该工作区的所有者，每个工作区每天最多收到一封此类提醒。',
    },
}


def warning_threshold(limit: int) -> int:
    return max(1, math.ceil(limit * WARNING_RATIO))


def render_quota_warning_email(
    *,
    workspace_name: str,
    used: int,
    limit: int,
    resets_at: datetime.datetime,
    message_language: str | None,
    plans_url: str | None,
) -> tuple[str, str, str]:
    """Return ``(subject, text, html)``."""

    lang = _TEXT[render.text_language(message_language)]
    percent = min(used * 100 // limit, 100) if limit > 0 else 100
    params = {
        'workspace': workspace_name,
        'used': used,
        'limit': limit,
        'remaining': max(limit - used, 0),
        'percent': percent,
        'reset_utc': resets_at.strftime('%Y-%m-%d %H:%M'),
        'reset_cst': (resets_at + datetime.timedelta(hours=8)).strftime('%H:%M'),
    }
    subject = lang['subject'].format(**params)
    intro = lang['intro'].format(**params)
    rows = [(label, value.format(**params)) for label, value in lang['rows']]

    meter = (
        '<tr><td style="padding:14px 16px 4px;">'
        '<div style="height:8px;background:#e8edf4;border-radius:4px;">'
        f'<div style="width:{percent}%;height:8px;background:#f59e0b;border-radius:4px;"></div></div></td></tr>'
    )
    rows_html = meter + ''.join(
        '<tr><td style="padding:10px 16px;border-top:1px solid #e8edf4;font-size:14px;">'
        f'<span style="color:#5f6f84;">{html.escape(label)}</span>'
        f'<span style="float:right;font-weight:700;color:#111827;">{html.escape(value)}</span></td></tr>'
        for label, value in rows
    )
    hint_html = (
        f'<p style="margin:20px 0 0;font-size:14px;line-height:1.7;color:#526173;">{html.escape(lang["hint"])}</p>'
    )
    body = render.render_layout(
        subject=subject,
        heading=lang['heading'],
        intro=intro,
        rows_html=rows_html,
        extra_html=hint_html,
        button_label=lang['open'],
        button_url=plans_url,
        footer=lang['footer'],
    )
    lines = [lang['heading'], '', intro, '']
    lines += [f'- {label}: {value}' for label, value in rows]
    lines += ['', lang['hint']]
    if plans_url:
        lines.append(f'{lang["open"]}: {plans_url}')
    lines += ['', lang['footer']]
    return subject, '\n'.join(lines) + '\n', body


def maybe_schedule(ap, workspace_uuid: str, *, used: int, limit: int, usage_date: datetime.date) -> None:
    """Start the warning task when this reservation reached the threshold."""

    if limit <= 0 or used < warning_threshold(limit) or (workspace_uuid, usage_date) in _settled:
        return
    task = asyncio.create_task(_warn(ap, workspace_uuid, used=used, limit=limit, usage_date=usage_date))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _warn(ap, workspace_uuid: str, *, used: int, limit: int, usage_date: datetime.date) -> None:
    try:
        if not await _claim(ap, workspace_uuid, usage_date):
            _settle(workspace_uuid, usage_date)
            return
        status = await send_warning(ap, workspace_uuid, used=used, limit=limit, usage_date=usage_date)
        if status == 'failed':
            # Release the claim so the next message retries delivery.
            await _set_claim(ap, workspace_uuid, usage_date, None)
        else:
            _settle(workspace_uuid, usage_date)
    except Exception as exc:
        _log(ap, f'Daily quota warning for Workspace {workspace_uuid} failed: {exc.__class__.__name__}: {exc}')


def _settle(workspace_uuid: str, usage_date: datetime.date) -> None:
    if len(_settled) > 50000:
        stale = {key for key in _settled if key[1] < usage_date}
        _settled.difference_update(stale or set(list(_settled)[:25000]))
    _settled.add((workspace_uuid, usage_date))


async def _claim(ap, workspace_uuid: str, usage_date: datetime.date) -> bool:
    statement = (
        sa.update(Usage)
        .where(
            Usage.workspace_uuid == workspace_uuid,
            Usage.usage_date == usage_date,
            Usage.quota_warning_at.is_(None),
        )
        .values(quota_warning_at=sa.func.now())
    )
    async with ap.persistence_mgr.tenant_write_uow(workspace_uuid, operation='message_quota.warning') as uow:
        result = await uow.execute(statement)
        return (result.rowcount or 0) > 0


async def _set_claim(ap, workspace_uuid: str, usage_date: datetime.date, value) -> None:
    statement = (
        sa.update(Usage)
        .where(Usage.workspace_uuid == workspace_uuid, Usage.usage_date == usage_date)
        .values(quota_warning_at=value)
    )
    async with ap.persistence_mgr.tenant_write_uow(workspace_uuid, operation='message_quota.warning') as uow:
        await uow.execute(statement)


async def owner_emails(ap, workspace_uuid: str) -> list[str]:
    statement = (
        sa.select(User.normalized_email)
        .join(WorkspaceMembership, User.uuid == WorkspaceMembership.account_uuid)
        .where(
            WorkspaceMembership.workspace_uuid == workspace_uuid,
            WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
            WorkspaceMembership.role == 'owner',
            User.status == AccountStatus.ACTIVE.value,
        )
        .order_by(WorkspaceMembership.created_at)
    )
    async with ap.persistence_mgr.tenant_uow(workspace_uuid) as uow:
        rows = (await uow.execute(statement)).scalars().all()
    return list(dict.fromkeys(email for email in rows if email and _EMAIL_RE.match(email)))


async def send_warning(ap, workspace_uuid: str, *, used: int, limit: int, usage_date: datetime.date) -> str:
    """Send the warning to every owner; returns sent | not_configured | no_recipients | failed."""

    email_service = EmailService(ap)
    if not email_service.capability()['enabled']:
        return 'not_configured'
    recipients = await owner_emails(ap, workspace_uuid)
    if not recipients:
        return 'no_recipients'
    workspace_name, language = await _workspace_identity(ap, workspace_uuid)
    resets_at = datetime.datetime.combine(usage_date + datetime.timedelta(days=1), datetime.time())
    subject, text, body = render_quota_warning_email(
        workspace_name=workspace_name,
        used=used,
        limit=limit,
        resets_at=resets_at,
        message_language=language,
        plans_url=plans_url(ap, workspace_uuid),
    )
    status = 'sent'
    for address in recipients:
        result = await email_service.send(
            to=[address], subject=subject, text=text, html=body, purpose='Daily quota warning email'
        )
        if result.status != 'sent':
            status = 'failed'
    return status


async def _workspace_identity(ap, workspace_uuid: str) -> tuple[str, str]:
    name = 'Workspace'
    try:
        workspace = await ap.workspace_service.get_workspace(workspace_uuid)
        name = str(getattr(workspace, 'name', '') or name)
    except Exception:
        pass
    language = 'en_US'
    try:
        from ..i18n.workspace import get_workspace_language

        language = await get_workspace_language(ap, workspace_uuid)
    except Exception:
        pass
    return name, language


def plans_url(ap, workspace_uuid: str) -> str | None:
    try:
        from ..workspace.invitation_delivery import InvitationDeliveryService

        base = InvitationDeliveryService(ap)._public_web_url().rstrip('/')
    except Exception:
        return None
    if not base or base.startswith('http://127.0.0.1') or base.startswith('http://localhost'):
        return None
    return f'{base}/home/monitoring?workspace={workspace_uuid}&open=plans'


def _log(ap, message: str) -> None:
    logger = getattr(ap, 'logger', None)
    if logger is not None:
        logger.warning(message)
