from __future__ import annotations

import asyncio
import dataclasses
import os
import smtplib
import ssl
import typing
from email.message import EmailMessage
from urllib.parse import quote

import httpx

from ..utils import httpclient

if typing.TYPE_CHECKING:
    from ..core.app import Application


DeliveryStatus = typing.Literal['sent', 'link_only', 'failed']


@dataclasses.dataclass(frozen=True, slots=True)
class InvitationDeliveryResult:
    status: DeliveryStatus
    provider: str | None

    def to_public_dict(self) -> dict[str, str | None]:
        return {'status': self.status, 'provider': self.provider}


@dataclasses.dataclass(frozen=True, slots=True)
class _EmailConfig:
    provider: typing.Literal['resend', 'smtp'] | None
    sender: str
    resend_api_key: str
    resend_api_url: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_starttls: bool
    smtp_ssl: bool
    timeout: float


class InvitationDeliveryService:
    """Optional Workspace invitation email delivery.

    The invitation link is always returned to the caller. Email failures are
    reported as non-secret status and never invalidate the persisted invite.
    """

    def __init__(self, ap: Application) -> None:
        self.ap = ap

    def capability(self) -> dict[str, str | bool | None]:
        config = self._email_config()
        return {'enabled': config.provider is not None, 'provider': config.provider}

    def build_invitation_link(self, token: str) -> str:
        base_url = self._public_web_url().rstrip('/')
        return f'{base_url}/invitations/accept#token={quote(token, safe="")}'

    async def deliver_invitation(
        self,
        *,
        recipient_email: str,
        workspace_name: str,
        invitation_link: str,
    ) -> InvitationDeliveryResult:
        config = self._email_config()
        if config.provider is None:
            return InvitationDeliveryResult(status='link_only', provider=None)

        try:
            if config.provider == 'resend':
                sent = await self._send_resend(config, recipient_email, workspace_name, invitation_link)
            else:
                sent = await self._send_smtp(config, recipient_email, workspace_name, invitation_link)
        except Exception as exc:
            self._log_delivery_failure(config.provider, exc)
            sent = False

        return InvitationDeliveryResult(
            status='sent' if sent else 'failed',
            provider=config.provider,
        )

    async def _send_resend(
        self,
        config: _EmailConfig,
        recipient_email: str,
        workspace_name: str,
        invitation_link: str,
    ) -> bool:
        payload = {
            'from': config.sender,
            'to': [recipient_email],
            'subject': f'You were invited to {workspace_name}',
            'text': self._plain_text(workspace_name, invitation_link),
            'html': self._html(workspace_name, invitation_link),
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            trust_env=True,
            event_hooks=httpclient.httpx_response_limit_hooks(),
        ) as client:
            response = await client.post(
                config.resend_api_url,
                headers={'Authorization': f'Bearer {config.resend_api_key}'},
                json=payload,
            )
        if response.status_code >= 400:
            self._log_delivery_failure(
                config.provider or 'resend', RuntimeError(f'Resend returned {response.status_code}')
            )
            return False
        return True

    async def _send_smtp(
        self,
        config: _EmailConfig,
        recipient_email: str,
        workspace_name: str,
        invitation_link: str,
    ) -> bool:
        message = EmailMessage()
        message['From'] = config.sender
        message['To'] = recipient_email
        message['Subject'] = f'You were invited to {workspace_name}'
        message.set_content(self._plain_text(workspace_name, invitation_link))
        message.add_alternative(self._html(workspace_name, invitation_link), subtype='html')

        return await asyncio.to_thread(self._send_smtp_sync, config, message)

    @staticmethod
    def _send_smtp_sync(config: _EmailConfig, message: EmailMessage) -> bool:
        smtp_cls = smtplib.SMTP_SSL if config.smtp_ssl else smtplib.SMTP
        context = ssl.create_default_context()
        with smtp_cls(config.smtp_host, config.smtp_port, timeout=config.timeout) as smtp:
            if config.smtp_starttls and not config.smtp_ssl:
                smtp.starttls(context=context)
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password)
            smtp.send_message(message)
        return True

    def _email_config(self) -> _EmailConfig:
        data = getattr(getattr(self.ap, 'instance_config', None), 'data', {}) or {}
        email = data.get('workspace', {}).get('invitations', {}).get('email', {})
        if not isinstance(email, dict):
            email = {}
        raw_provider = self._env('WORKSPACE__INVITATIONS__EMAIL__PROVIDER', email.get('provider', ''))
        raw_provider = str(raw_provider or '').strip().casefold()
        provider: typing.Literal['resend', 'smtp'] | None
        provider = raw_provider if raw_provider in {'resend', 'smtp'} else None
        sender = str(self._env('WORKSPACE__INVITATIONS__EMAIL__FROM', email.get('from', '')) or '').strip()
        timeout = self._number(
            self._env('WORKSPACE__INVITATIONS__EMAIL__TIMEOUT_SECONDS', email.get('timeout_seconds', 10)),
            10.0,
        )

        resend = email.get('resend', {})
        if not isinstance(resend, dict):
            resend = {}
        smtp_config = email.get('smtp', {})
        if not isinstance(smtp_config, dict):
            smtp_config = {}

        resend_api_key = str(
            self._env('WORKSPACE__INVITATIONS__EMAIL__RESEND__API_KEY', resend.get('api_key', '')) or ''
        ).strip()
        resend_api_url = str(
            self._env(
                'WORKSPACE__INVITATIONS__EMAIL__RESEND__API_URL',
                resend.get('api_url', 'https://api.resend.com/emails'),
            )
            or ''
        ).strip()
        smtp_host = str(
            self._env('WORKSPACE__INVITATIONS__EMAIL__SMTP__HOST', smtp_config.get('host', '')) or ''
        ).strip()
        smtp_port = int(
            self._number(self._env('WORKSPACE__INVITATIONS__EMAIL__SMTP__PORT', smtp_config.get('port', 587)), 587)
        )
        smtp_username = str(
            self._env('WORKSPACE__INVITATIONS__EMAIL__SMTP__USERNAME', smtp_config.get('username', '')) or ''
        ).strip()
        smtp_password = str(
            self._env('WORKSPACE__INVITATIONS__EMAIL__SMTP__PASSWORD', smtp_config.get('password', '')) or ''
        )
        smtp_starttls = self._bool(
            self._env('WORKSPACE__INVITATIONS__EMAIL__SMTP__STARTTLS', smtp_config.get('starttls', True))
        )
        smtp_ssl = self._bool(self._env('WORKSPACE__INVITATIONS__EMAIL__SMTP__SSL', smtp_config.get('ssl', False)))

        if provider == 'resend' and not (sender and resend_api_key and resend_api_url):
            provider = None
        elif provider == 'smtp' and not (sender and smtp_host):
            provider = None

        return _EmailConfig(
            provider=provider,
            sender=sender,
            resend_api_key=resend_api_key,
            resend_api_url=resend_api_url,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_starttls=smtp_starttls,
            smtp_ssl=smtp_ssl,
            timeout=timeout,
        )

    def _public_web_url(self) -> str:
        data = getattr(getattr(self.ap, 'instance_config', None), 'data', {}) or {}
        invitations = data.get('workspace', {}).get('invitations', {})
        configured = ''
        if isinstance(invitations, dict):
            configured = str(
                self._env('WORKSPACE__INVITATIONS__PUBLIC_WEB_URL', invitations.get('public_web_url', '')) or ''
            ).strip()
        if configured:
            return configured
        api = data.get('api', {})
        if isinstance(api, dict):
            webui_url = str(api.get('webui_url', '') or '').strip()
            if webui_url:
                return webui_url
            webhook_prefix = str(api.get('webhook_prefix', '') or '').strip()
            if webhook_prefix:
                return webhook_prefix
            port = api.get('port', 5300)
        else:
            port = 5300
        return f'http://127.0.0.1:{port}'

    @staticmethod
    def _plain_text(workspace_name: str, invitation_link: str) -> str:
        return (
            'You have been invited to LangBot Cloud\n\n'
            f'Join the Workspace “{workspace_name}” to collaborate with your team.\n\n'
            f'Accept invitation: {invitation_link}\n\n'
            'This secure invitation expires in 7 days and can only be accepted by the email address '
            'it was sent to. If you were not expecting it, you can safely ignore this email.\n'
        )

    @staticmethod
    def _html(workspace_name: str, invitation_link: str) -> str:
        import html

        escaped_workspace = html.escape(workspace_name, quote=True)
        escaped_link = html.escape(invitation_link, quote=True)
        return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Join {escaped_workspace} on LangBot Cloud</title>
</head>
<body style="margin:0;background:#f4f7fb;color:#152033;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">You have been invited to join {escaped_workspace} on LangBot Cloud.</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f7fb;padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border:1px solid #e5eaf2;border-radius:16px;overflow:hidden;box-shadow:0 12px 32px rgba(20,49,93,.08);">
        <tr><td style="padding:28px 36px;background:linear-gradient(135deg,#0f172a,#1d4ed8);color:#ffffff;">
          <div style="font-size:14px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;opacity:.78;">LangBot Cloud</div>
          <div style="font-size:26px;font-weight:700;margin-top:8px;line-height:1.25;">You’re invited</div>
        </td></tr>
        <tr><td style="padding:36px;">
          <p style="margin:0 0 18px;font-size:16px;line-height:1.65;color:#475569;">You have been invited to collaborate in this Workspace:</p>
          <div style="margin:0 0 26px;padding:18px 20px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;font-size:18px;font-weight:700;color:#0f172a;">{escaped_workspace}</div>
          <table role="presentation" cellspacing="0" cellpadding="0"><tr><td style="border-radius:9px;background:#2563eb;">
            <a href="{escaped_link}" style="display:inline-block;padding:13px 22px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;">Accept invitation</a>
          </td></tr></table>
          <p style="margin:26px 0 8px;font-size:14px;line-height:1.6;color:#64748b;">This invitation expires in 7 days and is bound to the email address that received it.</p>
          <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#94a3b8;">If the button does not work, copy and paste this URL into your browser:</p>
          <p style="margin:0;padding:12px;background:#f8fafc;border-radius:8px;word-break:break-all;font-size:12px;line-height:1.55;color:#475569;">{escaped_link}</p>
        </td></tr>
        <tr><td style="padding:20px 36px;border-top:1px solid #eef2f7;font-size:12px;line-height:1.6;color:#94a3b8;">If you were not expecting this invitation, you can safely ignore this email.</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''

    @staticmethod
    def _number(value: typing.Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _bool(value: typing.Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {'true', '1', 'yes', 'on'}
        return bool(value)

    @staticmethod
    def _env(name: str, fallback: typing.Any) -> typing.Any:
        value = os.environ.get(name)
        if value is None:
            return fallback
        return value

    def _log_delivery_failure(self, provider: str, exc: Exception) -> None:
        logger = getattr(self.ap, 'logger', None)
        if logger is not None:
            logger.warning(f'Workspace invitation email delivery via {provider} failed: {exc.__class__.__name__}')
