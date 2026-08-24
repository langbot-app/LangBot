from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.workspace.invitation_delivery import (
    InvitationDeliveryResult,
    InvitationDeliveryService,
)


pytestmark = pytest.mark.asyncio


def _app(config: dict) -> SimpleNamespace:
    return SimpleNamespace(
        instance_config=SimpleNamespace(data=config),
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )


async def test_link_only_delivery_builds_public_web_link_without_secret_capability():
    service = InvitationDeliveryService(
        _app(
            {
                'api': {
                    'webui_url': 'https://public.langbot.example/',
                    'webhook_prefix': 'http://internal:5300',
                }
            }
        )
    )

    assert service.build_invitation_link('lbi_secret') == (
        'https://public.langbot.example/invitations/accept#token=lbi_secret'
    )
    assert service.capability() == {'enabled': False, 'provider': None}
    result = await service.deliver_invitation(
        recipient_email='member@example.com',
        workspace_name='Workspace',
        invitation_link='https://public.langbot.example/invitations/accept#token=lbi_secret',
    )
    assert result == InvitationDeliveryResult(status='link_only', provider=None)


async def test_configured_provider_failure_returns_failed_without_raising():
    service = InvitationDeliveryService(
        _app(
            {
                'workspace': {
                    'invitations': {
                        'email': {
                            'provider': 'resend',
                            'from': 'LangBot <noreply@example.com>',
                            'resend': {'api_key': 'resend-secret'},
                        }
                    }
                }
            }
        )
    )
    service._send_resend = AsyncMock(return_value=False)

    assert service.capability() == {'enabled': True, 'provider': 'resend'}
    result = await service.deliver_invitation(
        recipient_email='member@example.com',
        workspace_name='Workspace',
        invitation_link='https://public.langbot.example/invitations/accept#token=lbi_secret',
    )

    assert result == InvitationDeliveryResult(status='failed', provider='resend')
    service._send_resend.assert_awaited_once()


async def test_environment_mapping_enables_provider_without_leaking_secret(monkeypatch):
    monkeypatch.setenv('WORKSPACE__INVITATIONS__PUBLIC_WEB_URL', 'https://env.langbot.example/')
    monkeypatch.setenv('WORKSPACE__INVITATIONS__EMAIL__PROVIDER', 'smtp')
    monkeypatch.setenv('WORKSPACE__INVITATIONS__EMAIL__FROM', 'LangBot <noreply@example.com>')
    monkeypatch.setenv('WORKSPACE__INVITATIONS__EMAIL__SMTP__HOST', 'smtp.example.com')
    monkeypatch.setenv('WORKSPACE__INVITATIONS__EMAIL__SMTP__PASSWORD', 'smtp-secret')
    service = InvitationDeliveryService(_app({'api': {'webui_url': 'https://config.example'}}))

    assert service.build_invitation_link('lbi_secret') == (
        'https://env.langbot.example/invitations/accept#token=lbi_secret'
    )
    assert service.capability() == {'enabled': True, 'provider': 'smtp'}


async def test_invitation_email_has_generic_langbot_brand_plain_fallback_and_expiry_copy():
    service = InvitationDeliveryService(_app({}))
    link = 'https://cloud.langbot.app/invitations/accept#token=lbi_secret&next=<unsafe>'

    text = service._plain_text('Research & Development', link)
    html = service._html('Research & Development', link)

    assert 'LangBot' in text
    assert 'LangBot Cloud' not in text
    assert 'Research & Development' in text
    assert '7 days' in text
    assert link in text
    assert 'Accept invitation' in html
    assert 'Research &amp; Development' in html
    assert 'expires in 7 days' in html
    assert 'lbi_secret&amp;next=&lt;unsafe&gt;' in html
    assert 'LangBot Cloud' not in html


async def test_invitation_email_uses_quiet_brand_lockup_and_compact_fallback_link():
    service = InvitationDeliveryService(_app({}))
    link = 'https://cloud.langbot.app/invitations/accept#token=lbi_secret'

    html = service._html("RockChinQ's Workspace", link)

    assert 'https://docs.langbot.app/langbot-logo.png' in html
    assert '>LangBot<' in html
    assert 'Workspace invitation' in html
    assert 'Open invitation link' in html
    assert 'linear-gradient' not in html
    assert 'box-shadow' not in html
    assert 'border-top:4px solid' not in html
    assert 'border:1px solid #dfe6f0' not in html
    assert 'height="28"' in html
    assert 'height="32"' in html
    assert 'margin-top:32px' not in html
    assert f'>{link}<' not in html


async def test_oss_smtp_configuration_delivers_the_generic_invitation_email():
    service = InvitationDeliveryService(
        _app(
            {
                'workspace': {
                    'invitations': {
                        'email': {
                            'provider': 'smtp',
                            'from': 'LangBot <noreply@example.com>',
                            'smtp': {'host': 'smtp.example.com'},
                        }
                    }
                }
            }
        )
    )
    service._send_smtp = AsyncMock(return_value=True)
    link = 'https://self-hosted.example/invitations/accept#token=lbi_secret'

    result = await service.deliver_invitation(
        recipient_email='member@example.com',
        workspace_name='Self-hosted Workspace',
        invitation_link=link,
    )

    assert result == InvitationDeliveryResult(status='sent', provider='smtp')
    service._send_smtp.assert_awaited_once()
    assert 'LangBot Cloud' not in service._plain_text('Self-hosted Workspace', link)
    assert 'LangBot Cloud' not in service._html('Self-hosted Workspace', link)
