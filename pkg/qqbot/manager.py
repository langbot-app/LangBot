import asyncio
import json
import os
import threading

import openai.error
from mirai import At, GroupMessage, MessageEvent, Mirai, Plain, StrangerMessage, WebSocketAdapter, FriendMessage, Image

import config
import pkg.openai.session
import pkg.openai.manager
from func_timeout import func_set_timeout, FunctionTimedOut
import datetime
import logging

import pkg.qqbot.filter

help_text = config.help_message

inst = None

processing = []


# 并行运行
def go(func, args=()):
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()


# 检查消息是否符合泛响应匹配机制
def check_response_rule(text: str) -> (bool, str):
    rules = config.response_rules
    # 检查前缀匹配
    for rule in rules['prefix']:
        if text.startswith(rule):
            return True, text.replace(rule, "", 1)

    # 检查正则表达式匹配
    for rule in rules['regex']:
        import re
        match = re.match(rule, text)
        if match:
            return True, match.group(1)

    return False, ""


# 控制QQ消息输入输出的类
class QQBotManager:
    timeout = 60
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

        bot = Mirai(
            qq=mirai_http_api_config['qq'],
            adapter=WebSocketAdapter(
                verify_key=mirai_http_api_config['verifyKey'],
                host=mirai_http_api_config['host'],
                port=mirai_http_api_config['port']
            )
        )

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

    # 统一的消息处理函数
    @func_set_timeout(timeout)
    def process_message(self, launcher_type: str, launcher_id: int, text_message: str) -> str:
        global processing
        reply = ''
        session_name = "{}_{}".format(launcher_type, launcher_id)

        pkg.openai.session.get_session(session_name).acquire_response_lock()

        try:
            if session_name in processing:
                pkg.openai.session.get_session(session_name).release_response_lock()
                return "[bot]err:正在处理中，请稍后再试"

            processing.append(session_name)

            try:

                if text_message.startswith('!') or text_message.startswith("！"):  # 指令
                    try:
                        logging.info(
                            "[{}]发起指令:{}".format(session_name, text_message[:min(20, len(text_message))] + (
                                "..." if len(text_message) > 20 else "")))

                        cmd = text_message[1:].strip().split(' ')[0]

                        params = text_message[1:].strip().split(' ')[1:]
                        if cmd == 'help':
                            reply = "[bot]" + help_text
                        elif cmd == 'reset':
                            pkg.openai.session.get_session(session_name).reset(explicit=True)
                            reply = "[bot]会话已重置"
                        elif cmd == 'last':
                            result = pkg.openai.session.get_session(session_name).last_session()
                            if result is None:
                                reply = "[bot]没有前一次的对话"
                            else:
                                datetime_str = datetime.datetime.fromtimestamp(result.create_timestamp).strftime(
                                    '%Y-%m-%d %H:%M:%S')
                                reply = "[bot]已切换到前一次的对话：\n创建时间:{}\n".format(
                                    datetime_str) + result.prompt[
                                                    :min(100,
                                                         len(result.prompt))] + \
                                        ("..." if len(result.prompt) > 100 else "#END#")
                        elif cmd == 'next':
                            result = pkg.openai.session.get_session(session_name).next_session()
                            if result is None:
                                reply = "[bot]没有后一次的对话"
                            else:
                                datetime_str = datetime.datetime.fromtimestamp(result.create_timestamp).strftime(
                                    '%Y-%m-%d %H:%M:%S')
                                reply = "[bot]已切换到后一次的对话：\n创建时间:{}\n".format(
                                    datetime_str) + result.prompt[
                                                    :min(100,
                                                         len(result.prompt))] + \
                                        ("..." if len(result.prompt) > 100 else "#END#")
                        elif cmd == 'prompt':
                            reply = "[bot]当前对话所有内容：\n" + pkg.openai.session.get_session(session_name).prompt
                        elif cmd == 'list':
                            pkg.openai.session.get_session(session_name).persistence()
                            page = 0

                            if len(params) > 0:
                                try:
                                    page = int(params[0])
                                except ValueError:
                                    pass

                            results = pkg.openai.session.get_session(session_name).list_history(page=page)
                            if len(results) == 0:
                                reply = "[bot]第{}页没有历史会话".format(page)
                            else:
                                reply = "[bot]历史会话 第{}页：\n".format(page)
                                current = -1
                                for i in range(len(results)):
                                    # 时间(使用create_timestamp转换) 序号 部分内容
                                    datetime_obj = datetime.datetime.fromtimestamp(results[i]['create_timestamp'])
                                    reply += "#{} 创建:{} {}\n".format(i + page * 10,
                                                                       datetime_obj.strftime("%Y-%m-%d %H:%M:%S"),
                                                                       results[i]['prompt'][
                                                                       :min(20, len(results[i]['prompt']))])
                                    if results[i]['create_timestamp'] == pkg.openai.session.get_session(
                                            session_name).create_timestamp:
                                        current = i + page * 10

                                reply += "\n以上信息倒序排列"
                                if current != -1:
                                    reply += ",当前会话是 #{}\n".format(current)
                                else:
                                    reply += ",当前处于全新会话或不在此页"
                        elif cmd == 'usage':
                            api_keys = pkg.openai.manager.get_inst().key_mgr.api_key
                            reply = "[bot]api-key使用情况:(阈值:{})\n\n".format(pkg.openai.manager.get_inst().key_mgr.api_key_usage_threshold)

                            using_key_name = ""
                            for api_key in api_keys:
                                reply += "{}:\n - {}字 {}%\n".format(api_key,
                                                               pkg.openai.manager.get_inst().key_mgr.get_usage(api_keys[api_key]),
                                                               round(pkg.openai.manager.get_inst().key_mgr.get_usage(api_keys[api_key]) / pkg.openai.manager.get_inst().key_mgr.api_key_usage_threshold * 100, 3))
                                if api_keys[api_key] == pkg.openai.manager.get_inst().key_mgr.using_key:
                                    using_key_name = api_key
                            reply += "\n当前使用:{}".format(using_key_name)
                    except Exception as e:
                        self.notify_admin("{}指令执行失败:{}".format(session_name, e))
                        logging.exception(e)
                        reply = "[bot]err:{}".format(e)
                else:  # 消息
                    logging.info("[{}]发送消息:{}".format(session_name, text_message[:min(20, len(text_message))] + (
                        "..." if len(text_message) > 20 else "")))

                    session = pkg.openai.session.get_session(session_name)
                    try:
                        prefix = "[GPT]" if hasattr(config, "show_prefix") and config.show_prefix else ""
                        reply = prefix + session.append(text_message)
                    except openai.error.APIConnectionError as e:
                        self.notify_admin("{}会话调用API失败:{}".format(session_name, e))
                        reply = "[bot]err:调用API失败，请重试或联系作者，或等待修复"
                    except openai.error.RateLimitError as e:
                        # 尝试切换api-key
                        pkg.openai.manager.get_inst().key_mgr.set_current_exceeded()
                        switched, name = pkg.openai.manager.get_inst().key_mgr.auto_switch()

                        if not switched:
                            self.notify_admin("API调用额度超限,请向OpenAI账户充值或在config.py中更换api_key")
                            reply = "[bot]err:API调用额度超额，请联系作者，或等待修复"
                        else:
                            self.notify_admin("API调用额度超限,已切换到{}".format(name))
                            reply = "[bot]err:API调用额度超额，已自动切换，请重新发送消息"
                    except openai.error.InvalidRequestError as e:
                        self.notify_admin("{}API调用参数错误:{}\n\n这可能是由于config.py中的prompt_submit_length参数或"
                                          "completion_api_params中的max_tokens参数数值过大导致的，请尝试将其降低".format(
                            session_name, e))
                        reply = "[bot]err:API调用参数错误，请联系作者，或等待修复"
                    except Exception as e:
                        logging.exception(e)
                        reply = "[bot]err:{}".format(e)

                logging.info(
                    "回复[{}]消息:{}".format(session_name,
                                             reply[:min(100, len(reply))] + ("..." if len(reply) > 100 else "")))
                reply = self.reply_filter.process(reply)

            finally:
                processing.remove(session_name)
        finally:
            pkg.openai.session.get_session(session_name).release_response_lock()

            return reply

    def send(self, event, msg):
        asyncio.run(self.bot.send(event, msg))

    # 私聊消息处理
    def on_person_message(self, event: MessageEvent):
        global processing

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
                        reply = self.process_message('person', event.sender.id, str(event.message_chain))
                        break
                    except FunctionTimedOut:
                        pkg.openai.session.get_session('person_{}'.format(event.sender.id)).release_response_lock()
                        failed += 1
                        continue

                if failed == self.retry:
                    pkg.openai.session.get_session('person_{}'.format(event.sender.id)).release_response_lock()
                    self.notify_admin("{} 请求超时".format("person_{}".format(event.sender.id)))
                    reply = "[bot]err:请求超时"

        if reply != '':
            return self.send(event, reply)

    # 群消息处理
    def on_group_message(self, event: GroupMessage):
        global processing

        reply = ''

        def process(text = None) -> str:
            replys = ""
            event.message_chain.remove(At(self.bot.qq))

            processing.append("group_{}".format(event.sender.id))

            # 超时则重试，重试超过次数则放弃
            failed = 0
            for i in range(self.retry):
                try:
                    replys = self.process_message('group', event.group.id,
                                                  str(event.message_chain).strip() if text is None else text)
                    break
                except FunctionTimedOut:
                    failed += 1
                    continue

            if failed == self.retry:
                self.notify_admin("{} 请求超时".format("group_{}".format(event.sender.id)))
                replys = "[bot]err:请求超时"

            return replys

        if Image in event.message_chain:
            pass
        elif At(self.bot.qq) not in event.message_chain:
            check, result = check_response_rule(str(event.message_chain).strip())

            if check:
                reply = process(result)
        else:
            # 直接调用
            reply = process()

        if reply != '':
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
