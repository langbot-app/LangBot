"""QQ group form replies preserve their native target and passive-reply anchor."""

import pytest

import langbot.pkg.core.app  # noqa: F401 -- initialize legacy platform registration
from langbot.pkg.platform.sources.qqofficial import QQOfficialAdapter
from tests.unit_tests.platform.test_qqofficial_full_group_messages import group_payload, receive_message


@pytest.mark.asyncio
@pytest.mark.parametrize('transport', ['gateway', 'webhook'])
@pytest.mark.parametrize('event_type', ['GROUP_MESSAGE_CREATE', 'GROUP_AT_MESSAGE_CREATE'])
async def test_group_form_reply_preserves_buttons_and_passive_reply_target(monkeypatch, transport, event_type):
    received, outbound = await receive_message(
        monkeypatch,
        QQOfficialAdapter,
        transport,
        event_type,
        group_payload(),
        form_data={
            'node_title': 'Choose an option',
            'form_content': 'Confirm this request',
            'actions': [{'id': 'confirm', 'title': 'Confirm'}],
        },
    )

    assert len(received) == 1
    assert len(outbound) == 1
    path, payload = outbound[0]
    assert path == '/v2/groups/group-one/messages'
    assert payload['msg_type'] == 2
    assert payload['msg_id'] == 'message-one'
    assert payload['markdown']['content'] == '### Choose an option\n\nConfirm this request'
    button = payload['keyboard']['content']['rows'][0]['buttons'][0]
    assert button['render_data']['label'] == 'Confirm'
    assert button['action']['data'] == 'confirm'
