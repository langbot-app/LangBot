"""Harness for the outer-stage behaviour baseline.

The baseline cases describe behaviour in terms of a *legacy* pipeline config
(the shape that carried ``trigger`` / ``safety`` / ``output`` before the
message policy existed). This module is the only place that knows how such a
config reaches the stages, so the same cases keep guarding behaviour while the
implementation underneath changes.
"""

from __future__ import annotations

import copy
import json
import typing
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import langbot.pkg.pipeline.pipelinemgr as pipelinemgr
from langbot.pkg.pipeline import aggregator as aggregator_module
from langbot.pkg.pipeline import stage as stage_module

import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

_TEMPLATE = Path(pipelinemgr.__file__).parents[2] / 'templates' / 'default-pipeline-config.json'

BOT_ACCOUNT_ID = 'bot-account'


def legacy_config(overrides: dict[str, typing.Any] | None = None) -> dict:
    """Return a full legacy pipeline config with dotted-path overrides applied."""
    config = json.loads(_TEMPLATE.read_text(encoding='utf-8'))
    # The baseline predates the trimmed template: pin the shipped defaults.
    config.setdefault(
        'trigger',
        {
            'group-respond-rules': {'at': True, 'prefix': ['ai'], 'regexp': [], 'random': 0.0},
            'access-control': {'mode': 'blacklist', 'blacklist': [], 'whitelist': []},
            'ignore-rules': {'prefix': [], 'regexp': []},
            'message-aggregation': {'enabled': False, 'delay': 1.5},
            'misc': {'combine-quote-message': True},
        },
    )
    config.setdefault(
        'safety',
        {
            'content-filter': {'scope': 'all', 'check-sensitive-words': True},
            'rate-limit': {'window-length': 60, 'limitation': 60, 'strategy': 'drop'},
        },
    )
    output = config.setdefault('output', {})
    output.setdefault('long-text-processing', {'threshold': 1000, 'strategy': 'none', 'font-path': ''})
    output.setdefault('force-delay', {'min': 0, 'max': 0})
    misc = output.setdefault('misc', {})
    for key, value in {
        'exception-handling': 'show-hint',
        'failure-hint': '',
        'at-sender': True,
        'quote-origin': True,
        'track-function-calls': False,
        'remove-think': False,
    }.items():
        misc.setdefault(key, value)
    for path, value in (overrides or {}).items():
        node = config
        parts = path.split('.')
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = copy.deepcopy(value)
    return config


def as_group(query, *, group_id: str = 'group-1', sender_id: str = 'member-1') -> None:
    """Turn the sample query into a group message from ``sender_id``."""
    group = platform_entities.Group(id=group_id, name='Group', permission=platform_entities.Permission.Member)
    sender = platform_entities.GroupMember(
        id=sender_id,
        member_name='Member',
        permission=platform_entities.Permission.Member,
        group=group,
    )
    query.launcher_type = provider_session.LauncherTypes.GROUP
    query.launcher_id = group_id
    query.sender_id = sender_id
    query.message_event = platform_events.GroupMessage(sender=sender, message_chain=query.message_chain, time=0)
    query.adapter.bot_account_id = BOT_ACCOUNT_ID


def set_text(query, *components) -> None:
    chain = platform_message.MessageChain(
        [platform_message.Plain(text=item) if isinstance(item, str) else item for item in components]
    )
    query.message_chain = chain
    query.message_event.message_chain = chain


def prepare_app(app) -> None:
    """Give the mock application the collaborators outer stages read."""
    app.sensitive_meta = Mock()
    app.sensitive_meta.data = {'words': ['badword'], 'mask': '*', 'mask_word': ''}
    app.platform_mgr = None
    app.bot_service = Mock(
        get_bot=AsyncMock(return_value={'command_settings': {'enabled': True, 'prefixes': ['/'], 'processors': []}})
    )


async def apply_legacy_config(app, query, config: dict) -> None:
    """Make ``config`` the configuration in effect for ``query``."""
    query.pipeline_config = config


async def build_stage(app, query, stage_name: str, config: dict):
    """Return an initialised stage that processes ``query`` under ``config``."""
    await apply_legacy_config(app, query, config)
    inst = stage_module.preregistered_stages[stage_name](app)
    await inst.initialize(config)
    return inst


async def run_stage(app, query, stage_name: str, config: dict):
    """Run one outer stage under a legacy config and return its result."""
    inst = await build_stage(app, query, stage_name, config)
    result = inst.process(query, stage_name)
    if isinstance(result, typing.Coroutine):
        result = await result
    return result


async def deliver_notice(app, query, config: dict, notice) -> None:
    """Deliver a stage user notice the way the stage chain does."""
    await apply_legacy_config(app, query, config)
    runtime = pipelinemgr.RuntimePipeline.__new__(pipelinemgr.RuntimePipeline)
    runtime.ap = app
    runtime._assert_execution_active = AsyncMock()
    from langbot.pkg.pipeline import entities

    await runtime._check_output(
        query,
        entities.StageProcessResult(
            result_type=entities.ResultType.INTERRUPT,
            new_query=query,
            user_notice=notice,
        ),
    )


async def aggregation_settings(app, query, config: dict) -> tuple[bool, float]:
    """Return (enabled, delay) the aggregator would use for this message."""
    app.pipeline_mgr = Mock()
    app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=Mock(pipeline_entity=Mock(config=config)))
    app.instance_config.data.setdefault('concurrency', {})
    aggregator = aggregator_module.MessageAggregator(app)
    return await aggregator._get_aggregation_config(query._execution_context, query.pipeline_uuid)
