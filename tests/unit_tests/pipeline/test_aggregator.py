"""
MessageAggregator unit tests.
"""

from importlib import import_module

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session


def test_merge_messages_preserves_routed_by_rule_if_any_input_matches(sample_message_event, mock_adapter):
    """Merged PendingMessage should keep routed_by_rule when any input was rule-routed."""
    aggregator = import_module('langbot.pkg.pipeline.aggregator')
    message_aggregator = aggregator.MessageAggregator(ap=None)

    first_message = aggregator.PendingMessage(
        bot_uuid='test-bot-uuid',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=12345,
        message_event=sample_message_event,
        message_chain=platform_message.MessageChain([platform_message.Plain(text='first')]),
        adapter=mock_adapter,
        pipeline_uuid='test-pipeline-uuid',
        routed_by_rule=False,
    )
    second_message = aggregator.PendingMessage(
        bot_uuid='test-bot-uuid',
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=12345,
        message_event=sample_message_event,
        message_chain=platform_message.MessageChain([platform_message.Plain(text='second')]),
        adapter=mock_adapter,
        pipeline_uuid='test-pipeline-uuid',
        routed_by_rule=True,
    )

    merged_message = message_aggregator._merge_messages([first_message, second_message])

    assert merged_message.routed_by_rule is True
    assert str(merged_message.message_chain) == 'first\nsecond'
