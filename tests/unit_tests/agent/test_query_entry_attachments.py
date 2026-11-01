"""Regression tests for missing media payloads at the event-first Runner boundary."""

from types import SimpleNamespace

from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter


def test_empty_content_element_does_not_hide_valid_message_chain_image():
    query = SimpleNamespace(
        message_chain=platform_message.MessageChain(
            [platform_message.Image(url='langbot-resource://image-1')]
        )
    )
    attachments = QueryEntryAdapter._build_attachments(
        query,
        [{'type': 'image_base64', 'image_base64': None}],
    )

    assert attachments == [
        {
            'type': 'image',
            'source': 'message_chain',
            'id': None,
            'url': 'langbot-resource://image-1',
            'content': None,
        }
    ]


def test_missing_content_or_url_does_not_create_uploadable_attachment():
    query = SimpleNamespace(message_chain=None)
    attachments = QueryEntryAdapter._build_attachments(
        query,
        [
            {'type': 'image_base64', 'image_base64': ''},
            {'type': 'image_url', 'image_url': {'url': None}},
            {'type': 'file_base64', 'file_base64': None, 'file_name': 'report.pdf'},
            {'type': 'file_url', 'file_url': None, 'file_name': 'report.pdf'},
        ],
    )

    assert attachments == []


def test_nonempty_contents_and_message_chain_media_are_preserved():
    query = SimpleNamespace(
        message_chain=platform_message.MessageChain(
            [platform_message.File(id='file-1', name='report.pdf')]
        )
    )
    attachments = QueryEntryAdapter._build_attachments(
        query,
        [
            {'type': 'image_base64', 'image_base64': 'data:image/png;base64,AAA='},
            {'type': 'file_url', 'file_url': 'https://example.test/report.pdf', 'file_name': 'report.pdf'},
        ],
    )

    assert [(item['type'], item['source']) for item in attachments] == [
        ('image', 'base64'),
        ('file', 'url'),
        ('file', 'message_chain'),
    ]
    assert attachments[-1]['id'] == 'file-1'
