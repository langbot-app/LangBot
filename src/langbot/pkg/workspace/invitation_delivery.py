from __future__ import annotations

import dataclasses
import os
import typing
from urllib.parse import quote

from ..notification.email import EmailService

if typing.TYPE_CHECKING:
    from ..core.app import Application


DeliveryStatus = typing.Literal['sent', 'link_only', 'failed']


@dataclasses.dataclass(frozen=True, slots=True)
class InvitationDeliveryResult:
    status: DeliveryStatus
    provider: str | None

    def to_public_dict(self) -> dict[str, str | None]:
        return {'status': self.status, 'provider': self.provider}


class InvitationDeliveryService:
    """Optional Workspace invitation email delivery.

    The invitation link is always returned to the caller. Email failures are
    reported as non-secret status and never invalidate the persisted invite.
    Delivery goes through the instance ``email`` service shared with alerts.
    """

    def __init__(self, ap: Application) -> None:
        self.ap = ap
        self._fallback_email = EmailService(ap)

    def _email(self) -> EmailService:
        return getattr(self.ap, 'email_service', None) or self._fallback_email

    def capability(self) -> dict[str, str | bool | None]:
        return self._email().capability()

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
        result = await self._email().send(
            to=[recipient_email],
            subject=f'You were invited to {workspace_name}',
            text=self._plain_text(workspace_name, invitation_link),
            html=self._html(workspace_name, invitation_link),
            purpose='Workspace invitation email',
        )
        if result.status == 'not_configured':
            return InvitationDeliveryResult(status='link_only', provider=None)
        return InvitationDeliveryResult(status=result.status, provider=result.provider)

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
            'You have been invited to join a Workspace in LangBot\n\n'
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
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Join {escaped_workspace} in LangBot</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fb;color:#111827;font-family:Arial,'Helvetica Neue',sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">You have been invited to join {escaped_workspace} in LangBot.</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f4f7fb;">
    <tr>
      <td align="center" style="padding:48px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;">
          <tr>
            <td style="padding:0 4px 20px;">
              <img src="https://langbot.app/docs/langbot-logo.png" alt="LangBot" width="34" height="34" style="display:inline-block;width:34px;height:34px;border:0;vertical-align:middle;">
              <span style="display:inline-block;margin-left:10px;vertical-align:middle;font-size:18px;font-weight:700;letter-spacing:-.01em;">LangBot</span>
            </td>
          </tr>
          <tr>
            <td style="background:#ffffff;border-radius:10px;overflow:hidden;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td style="padding:42px 42px 38px;">
                    <div style="margin:0 0 12px;font-size:13px;line-height:1.4;font-weight:600;color:#5f6f84;">Workspace invitation</div>
                    <h1 style="margin:0 0 16px;font-size:28px;line-height:1.25;font-weight:700;letter-spacing:-.025em;color:#111827;">You’re invited to collaborate</h1>
                    <p style="margin:0 0 28px;font-size:15px;line-height:1.7;color:#526173;">Join your team in LangBot and start building together in this Workspace.</p>

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f6f8fb;border-radius:8px;">
                      <tr>
                        <td style="padding:16px 18px;">
                          <div style="margin:0 0 4px;font-size:11px;line-height:1.4;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#5f6f84;">Workspace</div>
                          <div style="font-size:18px;line-height:1.4;font-weight:700;color:#111827;">{escaped_workspace}</div>
                        </td>
                      </tr>
                    </table>

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                      <tr><td height="28" style="height:28px;font-size:0;line-height:0;">&nbsp;</td></tr>
                    </table>

                    <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                      <tr>
                        <td style="background:#2563eb;border-radius:8px;">
                          <a href="{escaped_link}" target="_blank" style="display:inline-block;padding:13px 22px;font-size:15px;line-height:1.2;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">Accept invitation</a>
                        </td>
                      </tr>
                    </table>

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                      <tr><td height="32" style="height:32px;font-size:0;line-height:0;">&nbsp;</td></tr>
                    </table>

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-top:1px solid #e8edf4;">
                      <tr>
                        <td style="padding-top:22px;">
                          <p style="margin:0 0 10px;font-size:13px;line-height:1.6;color:#5f6f84;">For your security, this invitation expires in 7 days and only works for the email address that received it.</p>
                          <a href="{escaped_link}" target="_blank" style="font-size:13px;line-height:1.6;font-weight:600;color:#2563eb;text-decoration:none;">Open invitation link&nbsp;&rarr;</a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:20px 24px 0;font-size:12px;line-height:1.6;color:#5f6f84;">
              Sent by LangBot<br>
              If you were not expecting this invitation, you can safely ignore this email.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''

    @staticmethod
    def _env(name: str, fallback: typing.Any) -> typing.Any:
        value = os.environ.get(name)
        if value is None:
            return fallback
        return value
