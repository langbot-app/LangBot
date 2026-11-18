"""Instance email service shared by Workspace invitations and alert emails.

Configuration lives in the top-level ``email`` section of ``data/config.yaml``
(env: ``EMAIL__*``). Older releases kept the same keys under
``workspace.invitations.email`` (env: ``WORKSPACE__INVITATIONS__EMAIL__*``);
``LoadConfigStage`` moves that section on startup and both env prefixes keep
working, the new one taking precedence.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import os
import smtplib
import ssl
import typing
from email.message import EmailMessage

import httpx

from ..utils import httpclient

if typing.TYPE_CHECKING:
    from ..core.app import Application


EmailProvider = typing.Literal['resend', 'smtp']
SendStatus = typing.Literal['sent', 'not_configured', 'failed']

ENV_PREFIX = 'EMAIL__'
LEGACY_ENV_PREFIX = 'WORKSPACE__INVITATIONS__EMAIL__'

DEFAULT_EMAIL_CONFIG: dict[str, typing.Any] = {
    'provider': '',
    'from': '',
    'timeout_seconds': 10,
    'resend': {
        'api_url': 'https://api.resend.com/emails',
        'api_key': '',
    },
    'smtp': {
        'host': '',
        'port': 587,
        'username': '',
        'password': '',
        'starttls': True,
        'ssl': False,
    },
}


def _is_configured(section: typing.Any) -> bool:
    return isinstance(section, dict) and bool(str(section.get('provider') or '').strip())


def _deep_fill(target: dict, defaults: dict) -> dict:
    for key, default in defaults.items():
        if key not in target:
            target[key] = copy.deepcopy(default)
        elif isinstance(default, dict) and isinstance(target[key], dict):
            _deep_fill(target[key], default)
    return target


def migrate_email_config(cfg: dict) -> bool:
    """Move ``workspace.invitations.email`` to the top-level ``email`` section.

    Returns True when the config changed. A configured legacy section wins over
    an unconfigured new one; when both are configured the new one is kept.
    """

    changed = False
    workspace = cfg.get('workspace')
    invitations = workspace.get('invitations') if isinstance(workspace, dict) else None
    legacy = invitations.pop('email', None) if isinstance(invitations, dict) else None
    if legacy is not None:
        changed = True

    current = cfg.get('email')
    if not isinstance(current, dict):
        current = None
    if _is_configured(legacy) and not _is_configured(current):
        current = copy.deepcopy(legacy)
    if current is None:
        current = copy.deepcopy(legacy) if isinstance(legacy, dict) else {}
        changed = True
    before = copy.deepcopy(current)
    cfg['email'] = _deep_fill(current, DEFAULT_EMAIL_CONFIG)
    return changed or before != cfg['email']


def legacy_email_env_overrides(environ: typing.Mapping[str, str] | None = None) -> dict[str, str]:
    """Translate legacy ``WORKSPACE__INVITATIONS__EMAIL__*`` names to ``EMAIL__*``.

    A new-style variable always takes precedence over its legacy alias.
    """

    environ = os.environ if environ is None else environ
    aliases: dict[str, str] = {}
    for key, value in environ.items():
        if key.startswith(LEGACY_ENV_PREFIX):
            new_key = ENV_PREFIX + key[len(LEGACY_ENV_PREFIX) :]
            if new_key not in environ:
                aliases[new_key] = value
    return aliases


@dataclasses.dataclass(frozen=True, slots=True)
class EmailConfig:
    provider: EmailProvider | None
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


@dataclasses.dataclass(frozen=True, slots=True)
class EmailSendResult:
    status: SendStatus
    provider: str | None
    error: str | None = None


class EmailService:
    """Send transactional email through the instance-configured provider."""

    def __init__(self, ap: Application) -> None:
        self.ap = ap

    def capability(self) -> dict[str, typing.Any]:
        config = self.config()
        return {'enabled': config.provider is not None, 'provider': config.provider}

    def config(self) -> EmailConfig:
        data = getattr(getattr(self.ap, 'instance_config', None), 'data', {}) or {}
        section = data.get('email')
        if not _is_configured(section):
            # Not yet migrated (tests, embedded callers): honour the legacy key.
            legacy = data.get('workspace', {}).get('invitations', {}).get('email')
            if _is_configured(legacy) or not isinstance(section, dict):
                section = legacy
        if not isinstance(section, dict):
            section = {}

        def env(path: str, fallback: typing.Any) -> typing.Any:
            for prefix in (ENV_PREFIX, LEGACY_ENV_PREFIX):
                value = os.environ.get(prefix + path)
                if value is not None:
                    return value
            return fallback

        resend = section.get('resend') if isinstance(section.get('resend'), dict) else {}
        smtp_config = section.get('smtp') if isinstance(section.get('smtp'), dict) else {}

        raw_provider = str(env('PROVIDER', section.get('provider', '')) or '').strip().casefold()
        provider: EmailProvider | None = raw_provider if raw_provider in {'resend', 'smtp'} else None  # type: ignore[assignment]
        sender = str(env('FROM', section.get('from', '')) or '').strip()
        resend_api_key = str(env('RESEND__API_KEY', resend.get('api_key', '')) or '').strip()
        resend_api_url = str(
            env('RESEND__API_URL', resend.get('api_url', DEFAULT_EMAIL_CONFIG['resend']['api_url'])) or ''
        ).strip()
        smtp_host = str(env('SMTP__HOST', smtp_config.get('host', '')) or '').strip()

        if provider == 'resend' and not (sender and resend_api_key and resend_api_url):
            provider = None
        elif provider == 'smtp' and not (sender and smtp_host):
            provider = None

        return EmailConfig(
            provider=provider,
            sender=sender,
            resend_api_key=resend_api_key,
            resend_api_url=resend_api_url,
            smtp_host=smtp_host,
            smtp_port=int(_number(env('SMTP__PORT', smtp_config.get('port', 587)), 587)),
            smtp_username=str(env('SMTP__USERNAME', smtp_config.get('username', '')) or '').strip(),
            smtp_password=str(env('SMTP__PASSWORD', smtp_config.get('password', '')) or ''),
            smtp_starttls=_bool(env('SMTP__STARTTLS', smtp_config.get('starttls', True))),
            smtp_ssl=_bool(env('SMTP__SSL', smtp_config.get('ssl', False))),
            timeout=_number(env('TIMEOUT_SECONDS', section.get('timeout_seconds', 10)), 10.0),
        )

    async def send(
        self,
        *,
        to: list[str],
        subject: str,
        text: str,
        html: str,
        purpose: str = 'email',
    ) -> EmailSendResult:
        """Send one message; never raises and never reports secrets."""

        config = self.config()
        if config.provider is None:
            return EmailSendResult(status='not_configured', provider=None)
        recipients = [address for address in to if address]
        if not recipients:
            return EmailSendResult(status='failed', provider=config.provider, error='no_recipients')
        try:
            if config.provider == 'resend':
                error = await self._send_resend(config, recipients, subject, text, html)
            else:
                error = await self._send_smtp(config, recipients, subject, text, html)
        except Exception as exc:
            error = exc.__class__.__name__
        if error:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning(f'{purpose} delivery via {config.provider} failed: {error}')
            return EmailSendResult(status='failed', provider=config.provider, error=error)
        return EmailSendResult(status='sent', provider=config.provider)

    async def _send_resend(self, config: EmailConfig, to: list[str], subject: str, text: str, html: str) -> str | None:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            trust_env=True,
            event_hooks=httpclient.httpx_response_limit_hooks(),
        ) as client:
            response = await client.post(
                config.resend_api_url,
                headers={'Authorization': f'Bearer {config.resend_api_key}'},
                json={'from': config.sender, 'to': to, 'subject': subject, 'text': text, 'html': html},
            )
        if response.status_code >= 400:
            return f'resend_http_{response.status_code}'
        return None

    async def _send_smtp(self, config: EmailConfig, to: list[str], subject: str, text: str, html: str) -> str | None:
        message = EmailMessage()
        message['From'] = config.sender
        message['To'] = ', '.join(to)
        message['Subject'] = subject
        message.set_content(text)
        message.add_alternative(html, subtype='html')
        await asyncio.to_thread(self._send_smtp_sync, config, message)
        return None

    @staticmethod
    def _send_smtp_sync(config: EmailConfig, message: EmailMessage) -> None:
        smtp_cls = smtplib.SMTP_SSL if config.smtp_ssl else smtplib.SMTP
        context = ssl.create_default_context()
        kwargs: dict[str, typing.Any] = {'timeout': config.timeout}
        if config.smtp_ssl:
            kwargs['context'] = context
        with smtp_cls(config.smtp_host, config.smtp_port, **kwargs) as smtp:
            if config.smtp_starttls and not config.smtp_ssl:
                smtp.starttls(context=context)
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password)
            smtp.send_message(message)


def _number(value: typing.Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: typing.Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'true', '1', 'yes', 'on'}
    return bool(value)
