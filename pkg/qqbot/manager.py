from __future__ import annotations

import json
import os
import logging
import asyncio

from mirai import At, GroupMessage, MessageEvent, StrangerMessage, \
    FriendMessage, Image, MessageChain, Plain
import mirai
import func_timeout

from ..openai import session as openai_session

from ..qqbot import process as processor
from ..utils import context
from ..plugin import host as plugin_host
from ..plugin import models as plugin_models
import tips as tips_custom
from ..qqbot import adapter as msadapter
from .resprule import resprule
from .bansess import bansess
from .cntfilter import cntfilter
from .longtext import longtext
from .ratelim import ratelim

from ..core import app, entities as core_entities


# 控制QQ消息输入输出的类
class QQBotManager:
    retry = 3

    adapter: msadapter.MessageSourceAdapter = None

    bot_account_id: int = 0

    ban_person = []
    ban_group = []

    # modern
    ap: app.Application = None

    bansess_mgr: bansess.SessionBanManager = None
    cntfilter_mgr: cntfilter.ContentFilterManager = None
    longtext_pcs: longtext.LongTextProcessor = None
    resprule_chkr: resprule.GroupRespondRuleChecker = None
    ratelimiter: ratelim.RateLimiter = None

    def __init__(self, first_time_init=True, ap: app.Application = None):
        config = context.get_config_manager().data

        self.ap = ap
        self.bansess_mgr = bansess.SessionBanManager(ap)
        self.cntfilter_mgr = cntfilter.ContentFilterManager(ap)
        self.longtext_pcs = longtext.LongTextProcessor(ap)
        self.resprule_chkr = resprule.GroupRespondRuleChecker(ap)
        self.ratelimiter = ratelim.RateLimiter(ap)

        self.timeout = config['process_message_timeout']
        self.retry = config['retry_times']
    
    async def initialize(self):
        await self.bansess_mgr.initialize()
        await self.cntfilter_mgr.initialize()
        await self.longtext_pcs.initialize()
        await self.resprule_chkr.initialize()
        await self.ratelimiter.initialize()

        config = context.get_config_manager().data

        logging.debug("Use adapter:" + config['msg_source_adapter'])
        if config['msg_source_adapter'] == 'yirimirai':
            from pkg.qqbot.sources.yirimirai import YiriMiraiAdapter

            mirai_http_api_config = config['mirai_http_api_config']
            self.bot_account_id = config['mirai_http_api_config']['qq']
            self.adapter = YiriMiraiAdapter(mirai_http_api_config)
        elif config['msg_source_adapter'] == 'nakuru':
            from pkg.qqbot.sources.nakuru import NakuruProjectAdapter
            self.adapter = NakuruProjectAdapter(config['nakuru_config'])
            self.bot_account_id = self.adapter.bot_account_id
        
        # 保存 account_id 到审计模块
        from ..utils.center import apigroup
        apigroup.APIGroup._runtime_info['account_id'] = "{}".format(self.bot_account_id)

        context.set_qqbot_manager(self)

        # 注册诸事件
        # Caution: 注册新的事件处理器之后，请务必在unsubscribe_all中编写相应的取消订阅代码
        async def on_friend_message(event: FriendMessage):

            await self.ap.query_pool.add_query(
                launcher_type=core_entities.LauncherTypes.PERSON,
                launcher_id=event.sender.id,
                sender_id=event.sender.id,
                message_event=event,
                message_chain=event.message_chain
            )

        self.adapter.register_listener(
            FriendMessage,
            on_friend_message
        )

        async def on_stranger_message(event: StrangerMessage):
            
            await self.ap.query_pool.add_query(
                launcher_type=core_entities.LauncherTypes.PERSON,
                launcher_id=event.sender.id,
                sender_id=event.sender.id,
                message_event=event,
                message_chain=event.message_chain
            )

        # nakuru不区分好友和陌生人，故仅为yirimirai注册陌生人事件
        if config['msg_source_adapter'] == 'yirimirai':
            self.adapter.register_listener(
                StrangerMessage,
                on_stranger_message
            )

        async def on_group_message(event: GroupMessage):

            await self.ap.query_pool.add_query(
                launcher_type=core_entities.LauncherTypes.GROUP,
                launcher_id=event.group.id,
                sender_id=event.sender.id,
                message_event=event,
                message_chain=event.message_chain
            )

        self.adapter.register_listener(
            GroupMessage,
            on_group_message
        )

    async def send(self, event, msg, check_quote=True, check_at_sender=True):
        config = context.get_config_manager().data
        
        if check_at_sender and config['at_sender']:
            msg.insert(
                0,
                Plain(" \n")
            )

            # 当回复的正文中包含换行时，quote可能会自带at，此时就不再单独添加at，只添加换行
            if "\n" not in str(msg[1]) or config['msg_source_adapter'] == 'nakuru':
                msg.insert(
                    0,
                    At(
                        event.sender.id
                    )
                )

        await self.adapter.reply_message(
            event,
            msg,
            quote_origin=True if config['quote_origin'] and check_quote else False
        )

    async def common_process(
        self,
        launcher_type: str,
        launcher_id: int,
        text_message: str,
        message_chain: MessageChain,
        sender_id: int
    ) -> mirai.MessageChain:
        """
        私聊群聊通用消息处理方法
        """
        # 检查bansess
        if await self.bansess_mgr.is_banned(launcher_type, launcher_id, sender_id):
            self.ap.logger.info("根据禁用列表忽略{}_{}的消息".format(launcher_type, launcher_id))
            return []

        if mirai.Image in message_chain:
            return []
        elif sender_id == self.bot_account_id:
            return []
        else:
            # 超时则重试，重试超过次数则放弃
            failed = 0
            for i in range(self.retry):
                try:
                    reply = await processor.process_message(launcher_type, launcher_id, text_message, message_chain,
                                                        sender_id)
                    return reply
                
                # TODO openai 超时处理
                except func_timeout.FunctionTimedOut:
                    logging.warning("{}_{}: 超时，重试中({})".format(launcher_type, launcher_id, i))
                    openai_session.get_session("{}_{}".format(launcher_type, launcher_id)).release_response_lock()
                    if "{}_{}".format(launcher_type, launcher_id) in processor.processing:
                        processor.processing.remove("{}_{}".format(launcher_type, launcher_id))
                    failed += 1
                    continue

            if failed == self.retry:
                openai_session.get_session("{}_{}".format(launcher_type, launcher_id)).release_response_lock()
                await self.notify_admin("{} 请求超时".format("{}_{}".format(launcher_type, launcher_id)))
                reply = [tips_custom.reply_message]

    # 私聊消息处理
    async def on_person_message(self, event: MessageEvent):
        reply = ''

        reply = await self.common_process(
            launcher_type="person",
            launcher_id=event.sender.id,
            text_message=str(event.message_chain),
            message_chain=event.message_chain,
            sender_id=event.sender.id
        )

        if reply:
            await self.send(event, reply, check_quote=False, check_at_sender=False)

    # 群消息处理
    async def on_group_message(self, event: GroupMessage):
        reply = ''

        text = str(event.message_chain).strip()

        rule_check_res = await self.resprule_chkr.check(
            text,
            event.message_chain,
            event.group.id,
            event.sender.id
        )

        if rule_check_res.matching:
            text = str(rule_check_res.replacement).strip()
            reply = await self.common_process(
                launcher_type="group",
                launcher_id=event.group.id,
                text_message=text,
                message_chain=rule_check_res.replacement,
                sender_id=event.sender.id
            )

        if reply:
            await self.send(event, reply)

    # 通知系统管理员
    async def notify_admin(self, message: str):
        await self.notify_admin_message_chain(MessageChain([Plain("[bot]{}".format(message))]))

    async def notify_admin_message_chain(self, message: mirai.MessageChain):
        config = context.get_config_manager().data
        if config['admin_qq'] != 0 and config['admin_qq'] != []:
            logging.info("通知管理员:{}".format(message))

            admin_list = []

            if type(config['admin_qq']) == int:
                admin_list.append(config['admin_qq'])
            
            for adm in admin_list:
                self.adapter.send_message(
                    "person",
                    adm,
                    message
                )

    async def run(self):
        await self.adapter.run_async()
