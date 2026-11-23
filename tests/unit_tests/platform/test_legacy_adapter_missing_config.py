"""Legacy adapters must raise a real exception naming the missing config keys.

They used to ``raise`` a pydantic ``CommandError`` model, which is not a
``BaseException``; Python then replaced it with
``TypeError: exceptions must derive from BaseException`` and that opaque text
was what users saw as the bot load error.
"""

import pytest

import langbot.pkg.platform.botmgr  # noqa: F401  (load the platform package in its normal order)
from langbot.pkg.platform.sources.slack import SlackAdapter
from langbot.pkg.platform.sources.wecomcs import WecomCSAdapter


class _Logger:
    async def info(self, *args, **kwargs):
        pass

    async def debug(self, *args, **kwargs):
        pass

    async def warning(self, *args, **kwargs):
        pass

    async def error(self, *args, **kwargs):
        pass


@pytest.mark.parametrize(
    ('config', 'expected'),
    [
        ({}, 'Slack missing required config: bot_token, signing_secret'),
        ({'bot_token': 'x', 'socket_mode': True}, 'Slack missing required config: app_token'),
    ],
)
def test_slack_adapter_reports_missing_config(config, expected):
    with pytest.raises(ValueError) as exc_info:
        SlackAdapter(config=config, logger=_Logger())
    assert str(exc_info.value) == expected


def test_wecomcs_adapter_reports_missing_config():
    with pytest.raises(ValueError) as exc_info:
        WecomCSAdapter(config={'corpid': 'corp-id', 'secret': 'secret'}, logger=_Logger())
    assert str(exc_info.value) == 'WeComCS missing required config: token, EncodingAESKey'
