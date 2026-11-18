"""Alert email rendering for the instance mail service.

Emails never contain end-user conversation content: only the rule, the
affected bot/Pipeline/model name, counts and a redacted, truncated error
summary.
"""

from __future__ import annotations

import html
import typing

_TEXT = {
    'en': {
        'subject': {
            'fired': '[LangBot] {count} alert(s) in {workspace}',
            'reminder': '[LangBot] Still failing: {count} alert(s) in {workspace}',
            'resolved': '[LangBot] Resolved: {count} alert(s) in {workspace}',
            'test': '[LangBot] Test alert from {workspace}',
        },
        'heading': {
            'fired': 'Repeated failures detected',
            'reminder': 'These alerts are still firing',
            'resolved': 'These alerts have recovered',
            'test': 'Alert email test',
        },
        'intro': {
            'fired': 'LangBot detected repeated failures in Workspace “{workspace}”.',
            'reminder': 'The following alerts in Workspace “{workspace}” have not recovered yet.',
            'resolved': 'The following alerts in Workspace “{workspace}” stopped failing.',
            'test': 'Alert emails from Workspace “{workspace}” reach this mailbox. No action is needed.',
        },
        'rule': {
            'pipeline_failures': 'Pipeline failures',
            'model_failures': 'Model call failures',
            'bot_offline': 'Bot stopped with an error',
        },
        'events': '{count} failure(s), first at {opened_at} UTC',
        'open': 'Open LangBot',
        'footer': 'Sent by LangBot. Change alert rules and recipients in Settings → Alerts.',
    },
    'zh': {
        'subject': {
            'fired': '[LangBot] {workspace} 有 {count} 条告警',
            'reminder': '[LangBot] 仍未恢复：{workspace} 的 {count} 条告警',
            'resolved': '[LangBot] 已恢复：{workspace} 的 {count} 条告警',
            'test': '[LangBot] 来自 {workspace} 的测试告警',
        },
        'heading': {
            'fired': '检测到连续失败',
            'reminder': '以下告警仍未恢复',
            'resolved': '以下告警已恢复',
            'test': '告警邮件测试',
        },
        'intro': {
            'fired': 'LangBot 在工作区「{workspace}」中检测到连续失败。',
            'reminder': '工作区「{workspace}」中的以下告警尚未恢复。',
            'resolved': '工作区「{workspace}」中的以下告警已停止失败。',
            'test': '工作区「{workspace}」的告警邮件可以送达此邮箱，无需任何操作。',
        },
        'rule': {
            'pipeline_failures': '流水线处理失败',
            'model_failures': '模型调用失败',
            'bot_offline': '机器人异常退出',
        },
        'events': '{count} 次失败，首次发生于 {opened_at} UTC',
        'open': '打开 LangBot',
        'footer': '由 LangBot 发送。可在「设置 → 告警」中调整告警规则和收件人。',
    },
}


def text_language(message_language: str | None) -> str:
    return 'zh' if str(message_language or '').startswith('zh') else 'en'


def render_alert_email(
    *,
    kind: str,
    workspace_name: str,
    incidents: list[dict[str, typing.Any]],
    message_language: str | None,
    console_url: str | None,
) -> tuple[str, str, str]:
    """Return ``(subject, text, html)``."""

    lang = _TEXT[text_language(message_language)]
    params = {'workspace': workspace_name, 'count': len(incidents)}
    subject = lang['subject'][kind].format(**params)
    heading = lang['heading'][kind]
    intro = lang['intro'][kind].format(**params)

    lines = [heading, '', intro, '']
    rows = []
    for incident in incidents:
        rule_label = lang['rule'].get(incident['rule'], incident['rule'])
        title = f'{rule_label}: {incident["subject_name"]}'
        events = lang['events'].format(
            count=incident['event_count'], opened_at=incident['opened_at'][:16].replace('T', ' ')
        )
        summary = incident.get('error_summary') or ''
        lines.append(f'- {title}')
        lines.append(f'  {events}')
        if summary:
            lines.append(f'  {summary}')
        rows.append(
            '<tr><td style="padding:12px 16px;border-top:1px solid #e8edf4;">'
            f'<div style="font-size:14px;font-weight:700;color:#111827;">{html.escape(title)}</div>'
            f'<div style="margin-top:4px;font-size:12px;color:#5f6f84;">{html.escape(events)}</div>'
            + (
                f'<div style="margin-top:6px;font-size:12px;color:#526173;font-family:monospace;'
                f'word-break:break-all;">{html.escape(summary)}</div>'
                if summary
                else ''
            )
            + '</td></tr>'
        )
    if console_url:
        lines += ['', f'{lang["open"]}: {console_url}']
    lines += ['', lang['footer']]

    button = (
        f'<p style="margin:24px 0 0;"><a href="{html.escape(console_url, quote=True)}" target="_blank" '
        'style="display:inline-block;padding:11px 20px;background:#2563eb;color:#ffffff;border-radius:8px;'
        f'font-size:14px;font-weight:700;text-decoration:none;">{html.escape(lang["open"])}</a></p>'
        if console_url
        else ''
    )
    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f4f7fb;color:#111827;font-family:Arial,'Helvetica Neue',sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f7fb;">
<tr><td align="center" style="padding:40px 16px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;">
<tr><td style="padding:0 4px 18px;font-size:18px;font-weight:700;">LangBot</td></tr>
<tr><td style="background:#ffffff;border-radius:10px;padding:32px 32px 28px;">
<h1 style="margin:0 0 12px;font-size:22px;line-height:1.3;color:#111827;">{html.escape(heading)}</h1>
<p style="margin:0 0 20px;font-size:14px;line-height:1.7;color:#526173;">{html.escape(intro)}</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
 style="background:#f6f8fb;border-radius:8px;">{''.join(rows)}</table>
{button}
</td></tr>
<tr><td align="center" style="padding:18px 24px 0;font-size:12px;line-height:1.6;color:#5f6f84;">
{html.escape(lang['footer'])}</td></tr>
</table></td></tr></table></body></html>"""
    return subject, '\n'.join(lines) + '\n', body
