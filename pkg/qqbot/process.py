# 此模块提供了消息处理的具体逻辑的接口
import asyncio

from func_timeout import func_set_timeout
import logging

from mirai import MessageChain, Plain

# 这里不使用动态引入config
# 因为在这里动态引入会卡死程序
# 而此模块静态引用config与动态引入的表现一致
import config as config_init_import

import pkg.openai.session
import pkg.openai.manager
import pkg.utils.reloader
import pkg.utils.updater
import pkg.utils.context
import pkg.qqbot.message
import pkg.qqbot.command

import pkg.plugin.host as plugin_host
import pkg.plugin.models as plugin_models

processing = []


@func_set_timeout(config_init_import.process_message_timeout)
def process_message(launcher_type: str, launcher_id: int, text_message: str, message_chain: MessageChain,
                    sender_id: int) -> MessageChain:
    global processing

    mgr = pkg.utils.context.get_qqbot_manager()

    reply = []
    session_name = "{}_{}".format(launcher_type, launcher_id)

    # 检查发送方是否被禁用
    if pkg.utils.context.get_qqbot_manager().enable_banlist:
        if sender_id in pkg.utils.context.get_qqbot_manager().ban_person:
            logging.info("根据禁用列表忽略用户{}的消息".format(sender_id))
            return []
        if launcher_type == 'group' and launcher_id in pkg.utils.context.get_qqbot_manager().ban_group:
            logging.info("根据禁用列表忽略群{}的消息".format(launcher_id))
            return []

    # 检查是否被禁言
    if launcher_type == 'group':
        result = mgr.bot.member_info(target=launcher_id, member_id=mgr.bot.qq).get()
        result = asyncio.run(result)
        if result.mute_time_remaining > 0:
            logging.info("机器人被禁言,跳过消息处理(group_{},剩余{}s)".format(launcher_id,
                                                                                result.mute_time_remaining))
            return reply

    pkg.openai.session.get_session(session_name).acquire_response_lock()

    # 处理消息
    try:
        if session_name in processing:
            pkg.openai.session.get_session(session_name).release_response_lock()
            return MessageChain([Plain("[bot]err:正在处理中，请稍后再试")])

        config = pkg.utils.context.get_config()

        processing.append(session_name)
        try:
            if text_message.startswith('!') or text_message.startswith("！"):  # 指令
                # 触发插件事件
                args = {
                    'launcher_type': launcher_type,
                    'launcher_id': launcher_id,
                    'sender_id': sender_id,
                    'command': text_message[1:].strip().split(' ')[0],
                    'params': text_message[1:].strip().split(' ')[1:],
                    'text_message': text_message,
                    'is_admin': sender_id is config.admin_qq,
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
                    reply = pkg.qqbot.command.process_command(session_name, text_message,
                                                              mgr, config, launcher_type, launcher_id, sender_id)

            else:  # 消息
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

                if not event.is_prevented_default():
                    reply = pkg.qqbot.message.process_normal_message(text_message,
                                                                     mgr, config, launcher_type, launcher_id, sender_id)

            if reply is not None and type(reply[0]) == str:
                logging.info(
                    "回复[{}]文字消息:{}".format(session_name,
                                                 reply[0][:min(100, len(reply[0]))] + (
                                                     "..." if len(reply[0]) > 100 else "")))
                reply = [mgr.reply_filter.process(reply[0])]
            else:
                logging.info("回复[{}]图片消息:{}".format(session_name, reply))

        finally:
            processing.remove(session_name)
    finally:
        pkg.openai.session.get_session(session_name).release_response_lock()

        return MessageChain(reply)
