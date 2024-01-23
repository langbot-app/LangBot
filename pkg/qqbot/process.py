# 此模块提供了消息处理的具体逻辑的接口
import asyncio
import time
import traceback

import mirai
import logging

# 这里不使用动态引入config
# 因为在这里动态引入会卡死程序
# 而此模块静态引用config与动态引入的表现一致
# 已弃用，由于超时时间现已动态使用
# import config as config_init_import

from ..qqbot import ratelimit
from ..qqbot import command, message
from ..openai import session as openai_session
from ..utils import context

from ..plugin import host as plugin_host
from ..plugin import models as plugin_models
from ..qqbot import ignore
from ..qqbot import banlist
from ..qqbot import blob
import tips as tips_custom

processing = []


def is_admin(qq: int) -> bool:
    """兼容list和int类型的管理员判断"""
    config = context.get_config_manager().data
    if type(config['admin_qq']) == list:
        return qq in config['admin_qq']
    else:
        return qq == config['admin_qq']


async def process_message(launcher_type: str, launcher_id: int, text_message: str, message_chain: mirai.MessageChain,
                    sender_id: int) -> mirai.MessageChain:
    global processing

    mgr = context.get_qqbot_manager()

    reply = []
    session_name = "{}_{}".format(launcher_type, launcher_id)

    # 检查发送方是否被禁用
    if banlist.is_banned(launcher_type, launcher_id, sender_id):
        logging.info("根据禁用列表忽略{}_{}的消息".format(launcher_type, launcher_id))
        return []

    if ignore.ignore(text_message):
        logging.info("根据忽略规则忽略消息: {}".format(text_message))
        return []

    config = context.get_config_manager().data

    if not config['wait_last_done'] and session_name in processing:
        return mirai.MessageChain([mirai.Plain(tips_custom.message_drop_tip)])

    # 检查是否被禁言
    if launcher_type == 'group':
        is_muted = await mgr.adapter.is_muted(launcher_id)
        if is_muted:
            logging.info("机器人被禁言,跳过消息处理(group_{})".format(launcher_id))
            return reply

    if config['income_msg_check']:
        if mgr.reply_filter.is_illegal(text_message):
            return mirai.MessageChain(mirai.Plain("[bot] 消息中存在不合适的内容, 请更换措辞"))

    openai_session.get_session(session_name).acquire_response_lock()

    text_message = text_message.strip()


    # 为强制消息延迟计时
    start_time = time.time()

    # 处理消息
    try:

        processing.append(session_name)
        try:
            msg_type = ''
            if text_message.startswith('!') or text_message.startswith("！"):  # 命令
                msg_type = 'command'
                # 触发插件事件
                args = {
                    'launcher_type': launcher_type,
                    'launcher_id': launcher_id,
                    'sender_id': sender_id,
                    'command': text_message[1:].strip().split(' ')[0],
                    'params': text_message[1:].strip().split(' ')[1:],
                    'text_message': text_message,
                    'is_admin': is_admin(sender_id),
                }
                event = plugin_host.emit(plugin_models.PersonCommandSent
                                         if launcher_type == 'person'
                                         else plugin_models.GroupCommandSent, **args)

                if event.get_return_value("alter") is not None:
                    text_message = event.get_return_value("alter")

                # 取出插件提交的返回值赋值给reply
                if event.get_return_value("reply") is not None:
                    reply = event.get_return_value("reply")

                if not event.is_prevented_default():
                    reply = command.process_command(session_name, text_message,
                                                              mgr, config, launcher_type, launcher_id, sender_id, is_admin(sender_id))

            else:  # 消息
                msg_type = 'message'
                # 限速丢弃检查
                # print(ratelimit.__crt_minute_usage__[session_name])
                if config['rate_limit_strategy'] == "drop":
                    if ratelimit.is_reach_limit(session_name):
                        logging.info("根据限速策略丢弃[{}]消息: {}".format(session_name, text_message))

                        return mirai.MessageChain(["[bot]"+tips_custom.rate_limit_drop_tip]) if tips_custom.rate_limit_drop_tip != "" else []

                before = time.time()
                # 触发插件事件
                args = {
                    "launcher_type": launcher_type,
                    "launcher_id": launcher_id,
                    "sender_id": sender_id,
                    "text_message": text_message,
                }
                event = plugin_host.emit(plugin_models.PersonNormalMessageReceived
                                         if launcher_type == 'person'
                                         else plugin_models.GroupNormalMessageReceived, **args)

                if event.get_return_value("alter") is not None:
                    text_message = event.get_return_value("alter")

                # 取出插件提交的返回值赋值给reply
                if event.get_return_value("reply") is not None:
                    reply = event.get_return_value("reply")

                if not event.is_prevented_default():
                    reply = message.process_normal_message(text_message,
                                                                     mgr, config, launcher_type, launcher_id, sender_id)

                # 限速等待时间
                if config['rate_limit_strategy'] == "wait":
                    time.sleep(ratelimit.get_rest_wait_time(session_name, time.time() - before))
                
                ratelimit.add_usage(session_name)

            if reply is not None and len(reply) > 0 and (type(reply[0]) == str or type(reply[0]) == mirai.Plain):
                if type(reply[0]) == mirai.Plain:
                    reply[0] = reply[0].text
                logging.info(
                    "回复[{}]文字消息:{}".format(session_name,
                                                 reply[0][:min(100, len(reply[0]))] + (
                                                     "..." if len(reply[0]) > 100 else "")))
                if msg_type == 'message':
                    reply = [mgr.reply_filter.process(reply[0])]
                    
                reply = blob.check_text(reply[0])
            else:
                logging.info("回复[{}]消息".format(session_name))

        finally:
            processing.remove(session_name)
    finally:
        openai_session.get_session(session_name).release_response_lock()

    # 检查延迟时间
    if config['force_delay_range'][1] == 0:
        delay_time = 0
    else:
        import random

        # 从延迟范围中随机取一个值(浮点)
        rdm = random.uniform(config['force_delay_range'][0], config['force_delay_range'][1])

        spent = time.time() - start_time

        # 如果花费时间小于延迟时间，则延迟
        delay_time = rdm - spent if rdm - spent > 0 else 0

    # 延迟
    if delay_time > 0:
        logging.info("[风控] 强制延迟{:.2f}秒(如需关闭，请到config.py修改force_delay_range字段)".format(delay_time))
        time.sleep(delay_time)

    return mirai.MessageChain(reply)
