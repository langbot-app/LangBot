import asyncio
import json
import os
import threading

import openai.error
from mirai import At, GroupMessage, MessageEvent, Mirai, Plain, StrangerMessage, WebSocketAdapter, HTTPAdapter, \
    FriendMessage, Image

import config
import pkg.openai.session
import pkg.openai.manager
from func_timeout import FunctionTimedOut
import logging

import pkg.qqbot.filter
import pkg.qqbot.process as processor

inst = None


# 并行运行
def go(func, args=()):
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()


# 检查消息是否符合泛响应匹配机制
def check_response_rule(text: str) -> (bool, str):
    if not hasattr(config, 'response_rules'):
        return False, ''

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


# 控制QQ消息输入输出的类
class QQBotManager:
    retry = 3

    bot = None

    reply_filter = None

    def __init__(self, mirai_http_api_config: dict, timeout: int = 60, retry: int = 3):

        self.timeout = timeout
        self.retry = retry

        if os.path.exists("sensitive.json") \
                and config.sensitive_word_filter is not None \
                and config.sensitive_word_filter:
            with open("sensitive.json", "r", encoding="utf-8") as f:
                self.reply_filter = pkg.qqbot.filter.ReplyFilter(json.load(f)['words'])
        else:
            self.reply_filter = pkg.qqbot.filter.ReplyFilter([])

        if 'adapter' not in mirai_http_api_config or mirai_http_api_config['adapter'] == "WebSocketAdapter":
            bot = Mirai(
                qq=mirai_http_api_config['qq'],
                adapter=WebSocketAdapter(
                    verify_key=mirai_http_api_config['verifyKey'],
                    host=mirai_http_api_config['host'],
                    port=mirai_http_api_config['port']
                )
            )
        elif mirai_http_api_config['adapter'] == "HTTPAdapter":
            bot = Mirai(
                qq=mirai_http_api_config['qq'],
                adapter=HTTPAdapter(
                    verify_key=mirai_http_api_config['verifyKey'],
                    host=mirai_http_api_config['host'],
                    port=mirai_http_api_config['port']
                )
            )

        else:
            raise Exception("未知的适配器类型")

        @bot.on(FriendMessage)
        async def on_friend_message(event: FriendMessage):
            go(self.on_person_message, (event,))

        @bot.on(StrangerMessage)
        async def on_stranger_message(event: StrangerMessage):
            go(self.on_person_message, (event,))

        @bot.on(GroupMessage)
        async def on_group_message(event: GroupMessage):
            go(self.on_group_message, (event,))

        self.bot = bot

        global inst
        inst = self

    def send(self, event, msg):
        asyncio.run(self.bot.send(event, msg))

    # 私聊消息处理
    def on_person_message(self, event: MessageEvent):

        reply = ''

        if event.sender.id == self.bot.qq:
            pass
        else:
            if Image in event.message_chain:
                pass
            else:
                # 超时则重试，重试超过次数则放弃
                failed = 0
                for i in range(self.retry):
                    try:
                        reply = processor.process_message('person', event.sender.id, str(event.message_chain))
                        break
                    except FunctionTimedOut:
                        pkg.openai.session.get_session('person_{}'.format(event.sender.id)).release_response_lock()
                        failed += 1
                        continue

                if failed == self.retry:
                    pkg.openai.session.get_session('person_{}'.format(event.sender.id)).release_response_lock()
                    self.notify_admin("{} 请求超时".format("person_{}".format(event.sender.id)))
                    reply = ["[bot]err:请求超时"]

        if reply:
            return self.send(event, reply)

    # 群消息处理
    def on_group_message(self, event: GroupMessage):

        reply = ''

        def process(text=None) -> str:
            replys = ""
            if At(self.bot.qq) in event.message_chain:
                event.message_chain.remove(At(self.bot.qq))

            # 超时则重试，重试超过次数则放弃
            failed = 0
            for i in range(self.retry):
                try:
                    replys = processor.process_message('group', event.group.id,
                                                  str(event.message_chain).strip() if text is None else text)
                    break
                except FunctionTimedOut:
                    failed += 1
                    continue

            if failed == self.retry:
                self.notify_admin("{} 请求超时".format("group_{}".format(event.sender.id)))
                replys = ["[bot]err:请求超时"]

            return replys

        if Image in event.message_chain:
            pass
        elif At(self.bot.qq) not in event.message_chain:
            check, result = check_response_rule(str(event.message_chain).strip())

            if check:
                reply = process(result.strip())
        else:
            # 直接调用
            reply = process()

        if reply:
            return self.send(event, reply)

    # 通知系统管理员
    def notify_admin(self, message: str):
        if hasattr(config, "admin_qq") and config.admin_qq != 0:
            logging.info("通知管理员:{}".format(message))
            send_task = self.bot.send_friend_message(config.admin_qq, "[bot]{}".format(message))
            threading.Thread(target=asyncio.run, args=(send_task,)).start()


def get_inst() -> QQBotManager:
    global inst
    return inst
