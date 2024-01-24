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

from ..qqbot import filter as qqbot_filter
from ..qqbot import process as processor
from ..utils import context
from ..plugin import host as plugin_host
from ..plugin import models as plugin_models
import tips as tips_custom
from ..qqbot import adapter as msadapter
from . import resprule

from ..boot import app


# 控制QQ消息输入输出的类
class QQBotManager:
    retry = 3

    adapter: msadapter.MessageSourceAdapter = None

    bot_account_id: int = 0

    reply_filter = None

    enable_banlist = False

    enable_private = True
    enable_group = True

    ban_person = []
    ban_group = []

    def __init__(self, first_time_init=True, ap: app.Application = None):
        config = context.get_config_manager().data

        self.timeout = config['process_message_timeout']
        self.retry = config['retry_times']

        # 由于YiriMirai的bot对象是单例的，且shutdown方法暂时无法使用
        # 故只在第一次初始化时创建bot对象，重载之后使用原bot对象
        # 因此，bot的配置不支持热重载
        if first_time_init:
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
        else:
            self.adapter = context.get_qqbot_manager().adapter
            self.bot_account_id = context.get_qqbot_manager().bot_account_id
        
        # 保存 account_id 到审计模块
        from ..utils.center import apigroup
        apigroup.APIGroup._runtime_info['account_id'] = "{}".format(self.bot_account_id)

        context.set_qqbot_manager(self)

        # 注册诸事件
        # Caution: 注册新的事件处理器之后，请务必在unsubscribe_all中编写相应的取消订阅代码
        async def on_friend_message(event: FriendMessage):

            async def friend_message_handler():
                # 触发事件
                args = {
                    "launcher_type": "person",
                    "launcher_id": event.sender.id,
                    "sender_id": event.sender.id,
                    "message_chain": event.message_chain,
                }
                plugin_event = plugin_host.emit(plugin_models.PersonMessageReceived, **args)

                if plugin_event.is_prevented_default():
                    return

                await self.on_person_message(event)

            asyncio.create_task(friend_message_handler())
        self.adapter.register_listener(
            FriendMessage,
            on_friend_message
        )

        async def on_stranger_message(event: StrangerMessage):

            async def stranger_message_handler():
                # 触发事件
                args = {
                    "launcher_type": "person",
                    "launcher_id": event.sender.id,
                    "sender_id": event.sender.id,
                    "message_chain": event.message_chain,
                }
                plugin_event = plugin_host.emit(plugin_models.PersonMessageReceived, **args)

                if plugin_event.is_prevented_default():
                    return

                await self.on_person_message(event)

            asyncio.create_task(stranger_message_handler())
        # nakuru不区分好友和陌生人，故仅为yirimirai注册陌生人事件
        if config['msg_source_adapter'] == 'yirimirai':
            self.adapter.register_listener(
                StrangerMessage,
                on_stranger_message
            )

        async def on_group_message(event: GroupMessage):

            async def group_message_handler(event: GroupMessage):
                # 触发事件
                args = {
                    "launcher_type": "group",
                    "launcher_id": event.group.id,
                    "sender_id": event.sender.id,
                    "message_chain": event.message_chain,
                }
                plugin_event = plugin_host.emit(plugin_models.GroupMessageReceived, **args)

                if plugin_event.is_prevented_default():
                    return

                await self.on_group_message(event)

            asyncio.create_task(group_message_handler(event))
        self.adapter.register_listener(
            GroupMessage,
            on_group_message
        )

        def unsubscribe_all():
            """取消所有订阅

            用于在热重载流程中卸载所有事件处理器
            """
            self.adapter.unregister_listener(
                FriendMessage,
                on_friend_message
            )
            if config['msg_source_adapter'] == 'yirimirai':
                self.adapter.unregister_listener(
                    StrangerMessage,
                    on_stranger_message
                )
            self.adapter.unregister_listener(
                GroupMessage,
                on_group_message
            )

        self.unsubscribe_all = unsubscribe_all

        # 加载禁用列表
        if os.path.exists("banlist.py"):
            import banlist
            self.enable_banlist = banlist.enable
            self.ban_person = banlist.person
            self.ban_group = banlist.group
            logging.info("加载禁用列表: person: {}, group: {}".format(self.ban_person, self.ban_group))

            if hasattr(banlist, "enable_private"):
                self.enable_private = banlist.enable_private
            if hasattr(banlist, "enable_group"):
                self.enable_group = banlist.enable_group

        config = context.get_config_manager().data
        if os.path.exists("sensitive.json") \
                and config['sensitive_word_filter'] is not None \
                and config['sensitive_word_filter']:
            with open("sensitive.json", "r", encoding="utf-8") as f:
                sensitive_json = json.load(f)
                self.reply_filter = qqbot_filter.ReplyFilter(
                    sensitive_words=sensitive_json['words'],
                    mask=sensitive_json['mask'] if 'mask' in sensitive_json else '*',
                    mask_word=sensitive_json['mask_word'] if 'mask_word' in sensitive_json else ''
                )
        else:
            self.reply_filter = qqbot_filter.ReplyFilter([])

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

        config = context.get_config_manager().data

        if not self.enable_private:
            logging.debug("已在banlist.py中禁用所有私聊")

        else:
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
        
        if not self.enable_group:
            logging.debug("已在banlist.py中禁用所有群聊")

        else:
            do_req = False
            text = str(event.message_chain).strip()
            if At(self.bot_account_id) in event.message_chain and resprule.response_at(event.group.id):
                # 直接调用
                # reply = await process()
                event.message_chain.remove(At(self.bot_account_id))
                text = str(event.message_chain).strip()
                do_req = True
            else:
                check, result = resprule.check_response_rule(event.group.id, str(event.message_chain).strip())

                if check:
                    do_req = True
                    text = result.strip()
                # 检查是否随机响应
                elif resprule.random_responding(event.group.id):
                    logging.info("随机响应group_{}消息".format(event.group.id))
                    # reply = await process()
                    do_req = True

            if do_req:
                reply = await self.common_process(
                    launcher_type="group",
                    launcher_id=event.group.id,
                    text_message=text,
                    message_chain=event.message_chain,
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
