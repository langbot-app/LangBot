from __future__ import annotations

import json
import os
import logging
import asyncio
import traceback

from mirai import At, GroupMessage, MessageEvent, StrangerMessage, \
    FriendMessage, Image, MessageChain, Plain
import mirai
import func_timeout

from ..provider import session as openai_session

import tips as tips_custom
from ..platform import adapter as msadapter
from .ratelim import ratelim

from ..core import app, entities as core_entities
from ..plugin import events


# 控制QQ消息输入输出的类
class PlatformManager:
    
    adapter: msadapter.MessageSourceAdapter = None

    bot_account_id: int = 0

    # modern
    ap: app.Application = None

    ratelimiter: ratelim.RateLimiter = None

    def __init__(self, ap: app.Application = None):

        self.ap = ap
        self.ratelimiter = ratelim.RateLimiter(ap)
    
    async def initialize(self):
        await self.ratelimiter.initialize()

        config = self.ap.cfg_mgr.data

        logging.debug("Use adapter:" + config['msg_source_adapter'])
        if config['msg_source_adapter'] == 'yirimirai':
            from pkg.platform.sources.yirimirai import YiriMiraiAdapter

            mirai_http_api_config = config['mirai_http_api_config']
            self.bot_account_id = config['mirai_http_api_config']['qq']
            self.adapter = YiriMiraiAdapter(mirai_http_api_config)
        elif config['msg_source_adapter'] == 'nakuru':
            from pkg.platform.sources.nakuru import NakuruProjectAdapter
            self.adapter = NakuruProjectAdapter(config['nakuru_config'])
            self.bot_account_id = self.adapter.bot_account_id
        
        # 保存 account_id 到审计模块
        from ..audit.center import apigroup
        apigroup.APIGroup._runtime_info['account_id'] = "{}".format(self.bot_account_id)

        async def on_friend_message(event: FriendMessage):

            event_ctx = await self.ap.plugin_mgr.emit_event(
                event=events.PersonMessageReceived(
                    launcher_type='person',
                    launcher_id=event.sender.id,
                    sender_id=event.sender.id,
                    message_chain=event.message_chain,
                    query=None
                )
            )

            if not event_ctx.is_prevented_default():

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
            
            event_ctx = await self.ap.plugin_mgr.emit_event(
                event=events.PersonMessageReceived(
                    launcher_type='person',
                    launcher_id=event.sender.id,
                    sender_id=event.sender.id,
                    message_chain=event.message_chain,
                    query=None
                )
            )

            if not event_ctx.is_prevented_default():

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

            event_ctx = await self.ap.plugin_mgr.emit_event(
                event=events.GroupMessageReceived(
                    launcher_type='person',
                    launcher_id=event.sender.id,
                    sender_id=event.sender.id,
                    message_chain=event.message_chain,
                    query=None
                )
            )

            if not event_ctx.is_prevented_default():

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
        config = self.ap.cfg_mgr.data
        
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

    # 通知系统管理员
    async def notify_admin(self, message: str):
        await self.notify_admin_message_chain(MessageChain([Plain("[bot]{}".format(message))]))

    async def notify_admin_message_chain(self, message: mirai.MessageChain):
        config = self.ap.cfg_mgr.data
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
        try:
            await self.adapter.run_async()
        except Exception as e:
            self.ap.logger.error('平台适配器运行出错: ' + str(e))
            self.ap.logger.debug(f"Traceback: {traceback.format_exc()}")
