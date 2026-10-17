"""Small, dependency-free catalog for LangBot-owned runtime messages.

English message templates are the stable catalog IDs. Diagnostic text from
providers, plugins and validators is deliberately not translated.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
from pathlib import Path

DEFAULT_LANGUAGE = 'en_US'
SUPPORTED_LANGUAGES = ('en_US', 'zh_Hans', 'zh_Hant', 'ja_JP', 'es_ES', 'ru_RU', 'th_TH', 'vi_VN')
language = contextvars.ContextVar('langbot_message_language', default=DEFAULT_LANGUAGE)
_catalogs = {
    locale: json.loads((Path(__file__).parent / 'locales' / f'{locale}.json').read_text(encoding='utf-8'))
    for locale in SUPPORTED_LANGUAGES
}

# Normalize existing API wording at the response boundary. Only exact owned
# messages are matched; validators and third-party diagnostics pass through.
_ALIASES = {
    **{
        name: 'Resource not found'
        for name in (
            'bot not found',
            'model not found',
            'provider not found',
            'plugin not found',
            'Server not found',
            'Skill not found',
            'Pipeline not found',
            'pipeline not found',
            'knowledge base not found',
            'Knowledge base not found',
            'User not found',
            'Account not found',
            'agent not found',
            'API key not found',
            'Message not found',
            'Task not found',
            'Passkey not found',
            'Webhook not found',
            'Bot not found or not available',
            'Bot is unavailable',
            'WebSocket adapter not found',
            'adapter not found',
            'requester not found',
            'icon not found',
            'Session not found',
        )
    },
    'Unauthorized': 'Invalid authentication credentials',
    'No valid user token provided': 'Invalid authentication credentials',
    'No valid API key provided': 'Invalid authentication credentials',
    'Invalid username or password': 'Invalid authentication credentials',
    'Invalid TOTP code': 'Invalid TOTP or recovery code',
    'Too many attempts, try again later': 'Too many requests. Please try again later.',
    'The configured Agent runner is unavailable': 'Agent runner temporarily unavailable. Please try again.',
    'The configured Agent runner is not authorized': 'Agent runner not authorized for this pipeline.',
    'The Agent runner could not complete this test': 'Agent runner execution failed.',
    'Forbidden': 'Permission denied',
    'Member removal permission is required': 'Permission denied',
    'The Agent runner returned an invalid response': 'The Agent runner returned an invalid response.',
    'Invalid or expired state': 'Authorization failed. Please try signing in again.',
    'Space OAuth Workspace binding mismatch': 'Authorization failed. Please try signing in again.',
    'Space OAuth response is missing the Cloud Workspace binding': 'Authorization failed. Please try signing in again.',
    'Space launch requires Cloud mode': 'This feature is unavailable in this Workspace.',
    'An Account is required': 'Please sign in with your LangBot Account',
    'ChatGPT authorization requires an authorized workspace user': 'Permission denied',
    'ChatGPT authorization is busy. Please retry shortly.': 'Server is busy. Please try again later.',
    'ChatGPT authorization network error. Please retry.': 'Connection failed',
    'ChatGPT credential storage failed. Please retry.': 'Failed to save ChatGPT credentials. Please retry.',
    'ChatGPT Codex response was not completed': 'ChatGPT Codex response failed or was incomplete. Please retry.',
    'ChatGPT Codex stream ended before completion. Please retry.': 'ChatGPT Codex response failed or was incomplete. Please retry.',
    'Not permitted': 'Permission denied',
    'Unauthorized or session expired': 'Invalid authentication credentials',
    'TOTP is not enabled for that Account': 'TOTP is not enabled for this Account',
    'No pending TOTP enrolment for this Account': 'TOTP is not enabled for this Account',
    'Too many active credential exchanges': 'Server is busy. Please try again later.',
    'Timeout waiting for QR code': 'Request timed out',
    'Model availability is unavailable': 'This feature is unavailable in this Workspace.',
    'Survey not available': 'This feature is unavailable in this Workspace.',
    **{
        message: 'Submission failed. Please try again.'
        for message in (
            'Failed to submit response',
            'Failed to submit feedback',
            'Failed to dismiss',
        )
    },
    **{
        message: 'File size exceeds the limit.'
        for message in (
            'Image size exceeds 10MB limit.',
            'file size exceeds 10MB limit',
            'attachment too large',
        )
    },
    **{
        message: 'Authorization failed. Please try signing in again.'
        for message in (
            'Space launch failed',
            'Space OAuth failed',
            'LangBot Account binding failed',
            'Failed to get access token from Space',
            'ChatGPT returned an incomplete authorization. Please sign in again.',
            'ChatGPT authorization was cancelled or replaced. Please retry.',
            'ChatGPT returned an invalid authorization response',
            'ChatGPT returned an invalid device code',
            'ChatGPT returned an invalid device code expiry',
            'ChatGPT device authorization failed. Please start again.',
            'ChatGPT returned an incomplete device authorization',
            'ChatGPT token exchange failed. Please start sign-in again.',
        )
    },
}


def normalize_language(value: str | None) -> str:
    value = (value or '').replace('-', '_')
    aliases = {
        'zh_CN': 'zh_Hans',
        'zh_TW': 'zh_Hant',
        'en': 'en_US',
        'ja': 'ja_JP',
        'es': 'es_ES',
        'ru': 'ru_RU',
        'th': 'th_TH',
        'vi': 'vi_VN',
    }
    value = aliases.get(value, value)
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


@contextlib.contextmanager
def language_scope(locale: str):
    token = language.set(normalize_language(locale))
    try:
        yield
    finally:
        language.reset(token)


def t(message: str, *, locale: str | None = None, **params) -> str:
    selected = normalize_language(locale or language.get())
    # Preserve established English diagnostic wording and resource names.
    # Aliases only share translations; they do not rewrite the source language.
    key = _ALIASES.get(message, message)
    text = message if selected == DEFAULT_LANGUAGE else _catalogs[selected].get(key, message)
    return text.format(**params) if params else text


def error_text(code: int | str, message: str) -> str:
    """Stable business codes take precedence over variable diagnostic wording."""
    if language.get() == DEFAULT_LANGUAGE:
        return message
    messages = {
        'permission_denied': 'Permission denied',
        'resource_not_found': 'Resource not found',
        'membership_not_found': 'Resource not found',
        'invalid_authentication': 'Invalid authentication credentials',
        'task_capacity_exceeded': 'Server is busy. Please try again later.',
        'blocking_work_capacity_exceeded': 'Server is busy. Please try again later.',
        'edition_limit': 'This feature is unavailable in this Workspace.',
        'entitlement_unavailable': 'This feature is unavailable in this Workspace.',
        'last_owner_required': 'The Workspace must retain an owner.',
        'already_a_member': 'This user is already a member.',
        'invitation_email_mismatch': 'The invitation email does not match your Account',
        'totp_invalid_code': 'Invalid TOTP or recovery code',
        'totp_challenge_invalid': 'Invalid TOTP or recovery code',
        'totp_already_enrolled': 'TOTP is already enabled for this Account',
        'totp_not_enrolled': 'TOTP is not enabled for this Account',
    }
    if code in ('invitation_invalid', 'invitation_expired', 'invitation_revoked', 'invitation_used'):
        return t('Invalid or expired invitation')
    return t(messages.get(code, message))


def pipeline_notice(query, name: str, default: str, **params) -> str:
    """Empty overrides inherit the Workspace language; user text stays literal.

    Only documented placeholders are substituted, so arbitrary braces in custom
    messages cannot cause a formatting exception.
    """
    config = query.pipeline_config.get('output', {}).get('misc', {})
    custom = config.get(name)
    # This was the shipped default before language inheritance existed.
    if name == 'failure-hint' and custom == 'Request failed.':
        custom = None
    if not isinstance(custom, str) or not custom.strip():
        return t(default, **params)
    for key, value in params.items():
        custom = custom.replace('{' + key + '}', str(value))
    return custom
