import asyncio
import json
import os
import threading


from mirai import At, GroupMessage, MessageEvent, Mirai, StrangerMessage, WebSocketAdapter, HTTPAdapter, \
    FriendMessage, Image, MessageChain, Plain
from func_timeout import func_set_timeout

import pkg.openai.session
import pkg.openai.manager
from func_timeout import FunctionTimedOut
import logging

import pkg.qqbot.filter
import pkg.qqbot.process as processor
import pkg.utils.context

import pkg.plugin.host as plugin_host
import pkg.plugin.models as plugin_models
import tips as tips_custom

import pkg.qqbot.adapter as msadapter


# 检查消息是否符合泛响应匹配机制
def check_response_rule(text: str):
    config = pkg.utils.context.get_config()

    rules = config.response_rules
    # 检查前缀匹配
    if 'prefix' in rules:
        for rule in rules['prefix']:
            if text.startswith(rule):
                return True, text.replace(rule, "", 1)

    # 检查正则表达式匹配
    if 'regexp' in rules:
        for rule in rules['regexp']:
            import re
            match = re.match(rule, text)
            if match:
                return True, text

    return False, ""


def response_at():
    config = pkg.utils.context.get_config()
    if 'at' not in config.response_rules:
        return True

    return config.response_rules['at']


def random_responding():
    config = pkg.utils.context.get_config()
    if 'random_rate' in config.response_rules:
        import random
        return random.random() < config.response_rules['random_rate']
    return False


# 控制QQ消息输入输出的类
class QQBotManager:
    retry = 3

    adapter: msadapter.MessageSourceAdapter = None

    bot_account_id: int = 0

    reply_filter = None

    enable_banlist = False

    ban_person = []
    ban_group = []

    def __init__(self, first_time_init=True):
        import config

        mirai_http_api_config = config.mirai_http_api_config
        self.timeout = config.process_message_timeout
        self.retry = config.retry_times

        # 由于YiriMirai的bot对象是单例的，且shutdown方法暂时无法使用
        # 故只在第一次初始化时创建bot对象，重载之后使用原bot对象
        # 因此，bot的配置不支持热重载
        if first_time_init:
            if config.msg_source_adapter == 'yirimirai':
                from pkg.qqbot.sources.yirimirai import YiriMiraiAdapter
                self.bot_account_id = config.mirai_http_api_config['qq']
                self.adapter = YiriMiraiAdapter(mirai_http_api_config)
            elif config.msg_source_adapter == 'nakuru':
                pass
        else:
            self.adapter = pkg.utils.context.get_qqbot_manager().adapter

        pkg.utils.context.set_qqbot_manager(self)

        # 注册诸事件
        # Caution: 注册新的事件处理器之后，请务必在unsubscribe_all中编写相应的取消订阅代码
        def on_friend_message(event: FriendMessage):

            def friend_message_handler():
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

                self.on_person_message(event)

            pkg.utils.context.get_thread_ctl().submit_user_task(
                friend_message_handler,
            )
        self.adapter.register_listener(
            FriendMessage,
            on_friend_message
        )

        def on_stranger_message(event: StrangerMessage):

            def stranger_message_handler():
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

                self.on_person_message(event)

            pkg.utils.context.get_thread_ctl().submit_user_task(
                stranger_message_handler,
            )
        self.adapter.register_listener(
            StrangerMessage,
            on_stranger_message
        )

        def on_group_message(event: GroupMessage):

            def group_message_handler(event: GroupMessage):
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

                self.on_group_message(event)

            pkg.utils.context.get_thread_ctl().submit_user_task(
                group_message_handler,
                event
            )
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

        config = pkg.utils.context.get_config()
        if os.path.exists("sensitive.json") \
                and config.sensitive_word_filter is not None \
                and config.sensitive_word_filter:
            with open("sensitive.json", "r", encoding="utf-8") as f:
                sensitive_json = json.load(f)
                self.reply_filter = pkg.qqbot.filter.ReplyFilter(
                    sensitive_words=sensitive_json['words'],
                    mask=sensitive_json['mask'] if 'mask' in sensitive_json else '*',
                    mask_word=sensitive_json['mask_word'] if 'mask_word' in sensitive_json else ''
                )
        else:
            self.reply_filter = pkg.qqbot.filter.ReplyFilter([])

    def send(self, event, msg, check_quote=True):
        config = pkg.utils.context.get_config()
        self.adapter.reply_message(
            event,
            msg,
            quote_origin=True if config.quote_origin and check_quote else False
        )

    # 私聊消息处理
    def on_person_message(self, event: MessageEvent):
        import config
        reply = ''

        if event.sender.id == self.bot_account_id:
            pass
        else:
            if Image in event.message_chain:
                pass
            else:
                # 超时则重试，重试超过次数则放弃
                failed = 0
                for i in range(self.retry):
                    try:
                        
                        @func_set_timeout(config.process_message_timeout)
                        def time_ctrl_wrapper():
                            reply = processor.process_message('person', event.sender.id, str(event.message_chain),
                                                            event.message_chain,
                                                            event.sender.id)
                            return reply
                        
                        reply = time_ctrl_wrapper()
                        break
                    except FunctionTimedOut:
                        logging.warning("person_{}: 超时，重试中({})".format(event.sender.id, i))
                        pkg.openai.session.get_session('person_{}'.format(event.sender.id)).release_response_lock()
                        if "person_{}".format(event.sender.id) in pkg.qqbot.process.processing:
                            pkg.qqbot.process.processing.remove('person_{}'.format(event.sender.id))
                        failed += 1
                        continue

                if failed == self.retry:
                    pkg.openai.session.get_session('person_{}'.format(event.sender.id)).release_response_lock()
                    self.notify_admin("{} 请求超时".format("person_{}".format(event.sender.id)))
                    reply = [tips_custom.reply_message]

        if reply:
            return self.send(event, reply, check_quote=False)

    # 群消息处理
    def on_group_message(self, event: GroupMessage):
        import config
        reply = ''

        def process(text=None) -> str:
            replys = ""
            if At(self.bot_account_id) in event.message_chain:
                event.message_chain.remove(At(self.bot_account_id))

            # 超时则重试，重试超过次数则放弃
            failed = 0
            for i in range(self.retry):
                try:
                    @func_set_timeout(config.process_message_timeout)
                    def time_ctrl_wrapper():
                        replys = processor.process_message('group', event.group.id,
                                                        str(event.message_chain).strip() if text is None else text,
                                                        event.message_chain,
                                                        event.sender.id)
                        return replys
                    
                    replys = time_ctrl_wrapper()
                    break
                except FunctionTimedOut:
                    logging.warning("group_{}: 超时，重试中({})".format(event.group.id, i))
                    pkg.openai.session.get_session('group_{}'.format(event.group.id)).release_response_lock()
                    if "group_{}".format(event.group.id) in pkg.qqbot.process.processing:
                        pkg.qqbot.process.processing.remove('group_{}'.format(event.group.id))
                    failed += 1
                    continue

            if failed == self.retry:
                pkg.openai.session.get_session('group_{}'.format(event.group.id)).release_response_lock()
                self.notify_admin("{} 请求超时".format("group_{}".format(event.group.id)))
                replys = [tips_custom.replys_message]

            return replys

        if Image in event.message_chain:
            pass
        else:
            if At(self.bot_account_id) in event.message_chain and response_at():
                # 直接调用
                reply = process()
            else:
                check, result = check_response_rule(str(event.message_chain).strip())

                if check:
                    reply = process(result.strip())
                # 检查是否随机响应
                elif random_responding():
                    logging.info("随机响应group_{}消息".format(event.group.id))
                    reply = process()

        if reply:
            return self.send(event, reply)

    # 通知系统管理员
    def notify_admin(self, message: str):
        config = pkg.utils.context.get_config()
        if config.admin_qq != 0 and config.admin_qq != []:
            logging.info("通知管理员:{}".format(message))
            if type(config.admin_qq) == int:
                self.adapter.send_message(
                    "person",
                    config.admin_qq,
                    MessageChain([Plain("[bot]{}".format(message))])
                )
            else:
                for adm in config.admin_qq:
                    self.adapter.send_message(
                        "person",
                        adm,
                        MessageChain([Plain("[bot]{}".format(message))])
                    )

    def notify_admin_message_chain(self, message):
        config = pkg.utils.context.get_config()
        if config.admin_qq != 0 and config.admin_qq != []:
            logging.info("通知管理员:{}".format(message))
            if type(config.admin_qq) == int:
                self.adapter.send_message(
                    "person",
                    config.admin_qq,
                    message
                )
            else:
                for adm in config.admin_qq:
                    self.adapter.send_message(
                        "person",
                        adm,
                        message
                    )
