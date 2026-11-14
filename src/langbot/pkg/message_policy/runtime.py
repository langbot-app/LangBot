"""Compiled message policy: the checks and reply handling one route applies.

A runtime is built once per effective policy and holds the state that depends
on it (group rule matchers, the content filter chain, the long-text strategy).
Messaging stages call it in place; other processors call the same methods
around their own work.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import random
import traceback
import typing

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from . import schema

if typing.TYPE_CHECKING:
    from ..core import app


@dataclasses.dataclass
class AccessVerdict:
    """Outcome of an admission check."""

    allowed: bool
    console_notice: str = ''


@dataclasses.dataclass
class FilterVerdict:
    """Outcome of a content filter pass."""

    allowed: bool
    text: str = ''
    """The text to continue with; only meaningful when ``rewritten`` is set."""
    rewritten: bool = False
    user_notice: str = ''
    console_notice: str = ''


class MessagePolicyRuntime:
    """One effective message policy, ready to be applied to messages."""

    def __init__(
        self,
        ap: app.Application,
        policy: dict[str, typing.Any],
        *,
        bot_uuid: str = '',
        route_id: str | None = None,
        rate_limiter: typing.Any = None,
    ):
        self.ap = ap
        # The runtime owns its copy: compiling may adjust it (font fallback).
        self.policy = schema.coerce_policy(schema.merge_policy(schema.neutral_policy(), policy))
        self.bot_uuid = bot_uuid
        self.route_id = route_id
        self.rate_limiter = rate_limiter
        self.rule_matchers: list[typing.Any] = []
        self.filter_chain: list[typing.Any] = []
        self.long_text_strategy: typing.Any = None

    async def initialize(self) -> None:
        # Loading the stage registry first keeps the import order the
        # application uses; the leaf modules below depend on it.
        from ..pipeline import pipelinemgr  # noqa: F401
        from ..pipeline.cntfilter import filter as filter_model
        from ..pipeline.cntfilter import filters as filter_impls
        from ..pipeline.longtext import strategies as strategy_impls
        from ..pipeline.ratelimit import algos as algo_impls
        from ..pipeline.resprule import rule as rule_model
        from ..pipeline.resprule import rules as rule_impls
        from ..utils import importutil

        for package in (rule_impls, filter_impls, strategy_impls, algo_impls):
            importutil.import_modules_in_pkg(package)

        self.rule_matchers = []
        for rule_cls in rule_model.preregisetered_rules:
            matcher = rule_cls(self.ap)
            await matcher.initialize()
            self.rule_matchers.append(matcher)

        required = ['content-ignore']
        if self.policy['safety']['content-filter']['check-sensitive-words']:
            required.append('ban-word-filter')
        self.filter_chain = [cls(self.ap) for cls in filter_model.preregistered_filters if cls.name in required]
        for content_filter in self.filter_chain:
            await content_filter.initialize()

        await self._initialize_long_text()

        if self.rate_limiter is None:
            self.rate_limiter = await create_rate_limiter(self.ap)

    async def _initialize_long_text(self) -> None:
        from ..pipeline.longtext import strategy as strategy_model

        config = self.policy['output']['long-text-processing']
        if config['strategy'] == 'none':
            self.long_text_strategy = None
            return

        if config['strategy'] == 'image':
            use_font = config['font-path']
            try:
                if not os.path.exists(use_font):
                    if os.name == 'nt':
                        use_font = 'C:/Windows/Fonts/msyh.ttc'
                        if not os.path.exists(use_font):
                            self.ap.logger.warn(
                                'Font file not found, and Windows system font cannot be used, switch to forward message component to send long messages, you can adjust the related settings in the configuration file.'
                            )
                            config['blob_message_strategy'] = 'forward'
                        else:
                            self.ap.logger.info('Using Windows system font: ' + use_font)
                            config['font-path'] = use_font
                    else:
                        self.ap.logger.warn(
                            'Font file not found, and system font cannot be used, switch to forward message component to send long messages, you can adjust the related settings in the configuration file.'
                        )
                        config['strategy'] = 'forward'
            except Exception:
                traceback.print_exc()
                self.ap.logger.error(
                    'Failed to load font file ({}), switch to forward message component to send long messages, you can adjust the related settings in the configuration file.'.format(
                        use_font
                    )
                )
                config['strategy'] = 'forward'

        for strategy_cls in strategy_model.preregistered_strategies:
            if strategy_cls.name == config['strategy']:
                self.long_text_strategy = strategy_cls(self.ap)
                break
        else:
            raise ValueError(f'Long message processing strategy not found: {config["strategy"]}')

        await self.long_text_strategy.initialize()

    # ------------------------------------------------------------------ config

    def overlay(self, config: typing.Any) -> dict[str, typing.Any]:
        """Return ``config`` with this policy laid over it under the legacy key names."""
        return schema.overlay_policy(config, self.policy)

    def attach(self, query: pipeline_query.Query, config: typing.Any = None) -> None:
        """Bind this policy to a query and expose it through ``query.pipeline_config``."""
        object.__setattr__(query, '_message_policy', self)
        query.pipeline_config = self.overlay(query.pipeline_config if config is None else config)

    @property
    def quote_origin(self) -> bool:
        return self.policy['output']['misc']['quote-origin']

    @property
    def at_sender(self) -> bool:
        return self.policy['output']['misc']['at-sender']

    # ---------------------------------------------------------------- admission

    def check_access(
        self,
        launcher_type: str,
        launcher_id: typing.Any,
        sender_id: typing.Any,
    ) -> AccessVerdict:
        """Apply the session blacklist or whitelist."""
        access = self.policy['trigger']['access-control']
        mode = access['mode']
        sess_list = access[mode]

        found = False
        if (launcher_type == 'group' and 'group_*' in sess_list) or (
            launcher_type == 'person' and 'person_*' in sess_list
        ):
            found = True
        else:
            for sess in sess_list:
                if sess == f'{launcher_type}_{launcher_id}':
                    found = True
                    break
                # ``*_<id>`` covers a user in private chat and inside any group.
                if sess.startswith('*_') and (sess[2:] == str(launcher_id) or sess[2:] == str(sender_id)):
                    found = True
                    break

        allowed = found if mode == 'whitelist' else not found
        return AccessVerdict(
            allowed=allowed,
            console_notice=''
            if allowed
            else f'Ignore message according to access control: {launcher_type}_{launcher_id}',
        )

    async def match_group_rules(self, query: pipeline_query.Query) -> bool:
        """Return whether a group message satisfies the group respond rules.

        A matching rule may rewrite the message (the bot mention and a matched
        prefix are removed); the rewrite is applied to ``query.message_chain``.
        """
        rules = self.policy['trigger']['group-respond-rules']
        if rules.get('enabled', True) is False:
            return True
        for matcher in self.rule_matchers:
            res = await matcher.match(str(query.message_chain), query.message_chain, rules, query)
            if res.matching:
                query.message_chain = res.replacement
                return True
        return False

    # --------------------------------------------------------------- rate limit

    async def acquire_rate_limit(self, query: pipeline_query.Query) -> bool:
        """Take one slot in the session's window; False means the message is dropped."""
        if self.policy['safety']['rate-limit'].get('enabled', True) is False:
            return True
        return await self.rate_limiter.require_access(query, query.launcher_type.value, query.launcher_id)

    async def release_rate_limit(self, query: pipeline_query.Query) -> None:
        if self.policy['safety']['rate-limit'].get('enabled', True) is False:
            return
        await self.rate_limiter.release_access(query, query.launcher_type.value, query.launcher_id)

    # ----------------------------------------------------------- content filter

    async def filter_inbound(self, query: pipeline_query.Query, message: str) -> FilterVerdict:
        """Check an incoming text. Only a PASS from every filter lets it through."""
        from ..pipeline.cntfilter import entities as filter_entities

        if self.policy['safety']['content-filter']['scope'] == 'output-msg':
            return FilterVerdict(allowed=True)
        if not message.strip():
            return FilterVerdict(allowed=True)
        for content_filter in self.filter_chain:
            if filter_entities.EnableStage.PRE not in content_filter.enable_stages:
                continue
            result = await content_filter.process(query, message)
            if result.level in (filter_entities.ResultLevel.BLOCK, filter_entities.ResultLevel.MASKED):
                return FilterVerdict(
                    allowed=False,
                    user_notice=result.user_notice,
                    console_notice=result.console_notice,
                )
            if result.level == filter_entities.ResultLevel.PASS:
                message = result.replacement
        return FilterVerdict(allowed=True, text=message, rewritten=True)

    async def filter_outbound(self, query: pipeline_query.Query, message: str) -> FilterVerdict:
        """Check an outgoing text. Masked text passes; only a BLOCK stops it."""
        from ..pipeline.cntfilter import entities as filter_entities

        if self.policy['safety']['content-filter']['scope'] == 'income-msg':
            return FilterVerdict(allowed=True)
        message = message.strip()
        for content_filter in self.filter_chain:
            if filter_entities.EnableStage.POST not in content_filter.enable_stages:
                continue
            result = await content_filter.process(query, message)
            if result.level == filter_entities.ResultLevel.BLOCK:
                return FilterVerdict(
                    allowed=False,
                    user_notice=result.user_notice,
                    console_notice=result.console_notice,
                )
            if result.level in (filter_entities.ResultLevel.PASS, filter_entities.ResultLevel.MASKED):
                message = result.replacement
        return FilterVerdict(allowed=True, text=message, rewritten=True)

    # ---------------------------------------------------------------- long text

    async def process_long_text(
        self,
        query: pipeline_query.Query,
        message_chain: platform_message.MessageChain,
    ) -> platform_message.MessageChain:
        """Return the chain to send: converted when it is plain text over the threshold."""
        if self.long_text_strategy is None:
            self.ap.logger.debug('Long message processing strategy is not set, skip long message processing.')
            return message_chain

        if any(not isinstance(component, platform_message.Plain) for component in message_chain):
            self.ap.logger.debug('Message contains non-Plain components, skip long message processing.')
            return message_chain

        if len(str(message_chain)) > self.policy['output']['long-text-processing']['threshold']:
            return platform_message.MessageChain(await self.long_text_strategy.process(str(message_chain), query))
        return message_chain

    # ------------------------------------------------------------------ sending

    async def wait_force_delay(self) -> None:
        """Sleep for the configured forced reply delay."""
        delay = self.policy['output']['force-delay']
        random_delay = random.uniform(delay['min'], delay['max'])
        self.ap.logger.debug('根据规则强制延迟回复: %s s', random_delay)
        await asyncio.sleep(random_delay)

    def mention_sender(
        self,
        message_event: typing.Any,
        message_chain: platform_message.MessageChain,
    ) -> None:
        """Prepend an @sender to a group reply when the policy asks for it."""
        if self.at_sender and isinstance(message_event, platform_events.GroupMessage):
            message_chain.insert(0, platform_message.At(target=message_event.sender.id))

    async def send_reply(self, query: pipeline_query.Query) -> None:
        """Send the latest reply chain of a query back to its conversation."""
        from ..pipeline import plugin_diagnostics

        await self.wait_force_delay()
        self.mention_sender(query.message_event, query.resp_message_chain[-1])

        quote_origin = self.quote_origin

        has_chunks = any(isinstance(msg, provider_message.MessageChunk) for msg in query.resp_messages)
        response_index = len(query.resp_message_chain) - 1
        message_chain = query.resp_message_chain[-1]

        is_streaming_response = False
        is_final = False
        try:
            is_streaming_response = await query.adapter.is_stream_output_supported() and has_chunks
            if is_streaming_response:
                is_final = query.resp_messages[-1].is_final
                await query.adapter.reply_message_chunk(
                    message_source=query.message_event,
                    bot_message=query.resp_messages[-1],
                    message=message_chain,
                    quote_origin=quote_origin,
                    is_final=is_final,
                )
            else:
                await query.adapter.reply_message(
                    message_source=query.message_event,
                    message=message_chain,
                    quote_origin=quote_origin,
                )
        except Exception as e:
            await plugin_diagnostics.notify_response_delivery_failure(
                self.ap,
                query,
                response_index,
                message_chain,
                e,
            )
            plugin_diagnostics.clear_response_source(query, response_index)
            if is_streaming_response:
                self.ap.logger.warning(
                    'Streaming response delivery failed; continuing runner event consumption: %s',
                    e,
                )
                if is_final:
                    try:
                        await query.adapter.reply_message(
                            message_source=query.message_event,
                            message=message_chain,
                            quote_origin=quote_origin,
                        )
                    except Exception as fallback_error:
                        self.ap.logger.warning(
                            'Final non-streaming response fallback also failed: %s',
                            fallback_error,
                        )
                return
            raise
        plugin_diagnostics.clear_response_source(query, response_index)

    def build_notice(
        self,
        message_event: typing.Any,
        notice: typing.Any,
    ) -> platform_message.MessageChain:
        """Turn a user notice into the chain to send, with @sender applied."""
        if isinstance(notice, str):
            notice = platform_message.MessageChain([platform_message.Plain(text=notice)])
        elif isinstance(notice, list):
            notice = platform_message.MessageChain(*notice)
        self.mention_sender(message_event, notice)
        return notice

    async def send_notice(
        self,
        query: pipeline_query.Query,
        notice: platform_message.MessageChain,
        *,
        before_send: typing.Callable[[], typing.Awaitable[typing.Any]] | None = None,
    ) -> None:
        """Send a prepared user notice (hint, error) to the conversation."""
        stream_output_supported = await query.adapter.is_stream_output_supported()
        if before_send is not None:
            await before_send()
        if stream_output_supported and query.resp_messages:
            await query.adapter.reply_message_chunk(
                message_source=query.message_event,
                bot_message=query.resp_messages[-1],
                message=notice,
                quote_origin=self.quote_origin,
                is_final=query.resp_messages[-1].is_final,
            )
        else:
            await query.adapter.reply_message(
                message_source=query.message_event,
                message=notice,
                quote_origin=self.quote_origin,
            )


async def create_rate_limiter(ap: app.Application) -> typing.Any:
    """Create the session rate limiter shared by every policy of an application."""
    from ..pipeline import pipelinemgr  # noqa: F401
    from ..pipeline.ratelimit import algo as algo_model
    from ..pipeline.ratelimit import algos as algo_impls
    from ..utils import importutil

    importutil.import_modules_in_pkg(algo_impls)
    algo_name = 'fixwin'
    for algo_cls in algo_model.preregistered_algos:
        if algo_cls.name == algo_name:
            limiter = algo_cls(ap)
            await limiter.initialize()
            return limiter
    raise ValueError(f'未知的限速算法: {algo_name}')
