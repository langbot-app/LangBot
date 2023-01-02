# 此模块提供了消息处理的具体逻辑的接口
import asyncio
import datetime
import threading

from func_timeout import func_set_timeout
import logging
import openai

from mirai import Image, MessageChain

import config

import pkg.openai.session
import pkg.openai.manager
import pkg.utils.reloader
import pkg.utils.updater
import pkg.utils.context

processing = []


@func_set_timeout(config.process_message_timeout)
def process_message(launcher_type: str, launcher_id: int, text_message: str, message_chain: MessageChain,
                    sender_id: int) -> MessageChain:
    global processing

    mgr = pkg.utils.context.get_qqbot_manager()

    reply = []
    session_name = "{}_{}".format(launcher_type, launcher_id)

    # 检查是否被禁言
    if launcher_type == 'group':
        result = mgr.bot.member_info(target=launcher_id, member_id=mgr.bot.qq).get()
        result = asyncio.run(result)
        if result.mute_time_remaining > 0:
            logging.info("机器人被禁言,跳过消息处理(group_{},剩余{}s)".format(launcher_id,
                                                                                  result.mute_time_remaining))
            return reply

    pkg.openai.session.get_session(session_name).acquire_response_lock()

    try:
        if session_name in processing:
            pkg.openai.session.get_session(session_name).release_response_lock()
            return ["[bot]err:正在处理中，请稍后再试"]

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
                        reply = ["[bot]" + config.help_message]
                    elif cmd == 'reset':
                        pkg.openai.session.get_session(session_name).reset(explicit=True)
                        reply = ["[bot]会话已重置"]
                    elif cmd == 'last':
                        result = pkg.openai.session.get_session(session_name).last_session()
                        if result is None:
                            reply = ["[bot]没有前一次的对话"]
                        else:
                            datetime_str = datetime.datetime.fromtimestamp(result.create_timestamp).strftime(
                                '%Y-%m-%d %H:%M:%S')
                            reply = ["[bot]已切换到前一次的对话：\n创建时间:{}\n".format(
                                datetime_str) + result.prompt[
                                                :min(100,
                                                     len(result.prompt))] + \
                                     ("..." if len(result.prompt) > 100 else "#END#")]
                    elif cmd == 'next':
                        result = pkg.openai.session.get_session(session_name).next_session()
                        if result is None:
                            reply = ["[bot]没有后一次的对话"]
                        else:
                            datetime_str = datetime.datetime.fromtimestamp(result.create_timestamp).strftime(
                                '%Y-%m-%d %H:%M:%S')
                            reply = ["[bot]已切换到后一次的对话：\n创建时间:{}\n".format(
                                datetime_str) + result.prompt[
                                                :min(100,
                                                     len(result.prompt))] + \
                                     ("..." if len(result.prompt) > 100 else "#END#")]
                    elif cmd == 'prompt':
                        reply = ["[bot]当前对话所有内容：\n" + pkg.openai.session.get_session(session_name).prompt]
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
                            reply = ["[bot]第{}页没有历史会话".format(page)]
                        else:
                            reply_str = "[bot]历史会话 第{}页：\n".format(page)
                            current = -1
                            for i in range(len(results)):
                                # 时间(使用create_timestamp转换) 序号 部分内容
                                datetime_obj = datetime.datetime.fromtimestamp(results[i]['create_timestamp'])
                                reply_str += "#{} 创建:{} {}\n".format(i + page * 10,
                                                                       datetime_obj.strftime("%Y-%m-%d %H:%M:%S"),
                                                                       results[i]['prompt'][
                                                                       :min(20, len(results[i]['prompt']))])
                                if results[i]['create_timestamp'] == pkg.openai.session.get_session(
                                        session_name).create_timestamp:
                                    current = i + page * 10

                            reply_str += "\n以上信息倒序排列"
                            if current != -1:
                                reply_str += ",当前会话是 #{}\n".format(current)
                            else:
                                reply_str += ",当前处于全新会话或不在此页"

                            reply = [reply_str]
                    elif cmd == 'usage':
                        api_keys = pkg.utils.context.get_openai_manager().key_mgr.api_key
                        reply_str = "[bot]api-key使用情况:(阈值:{})\n\n".format(
                            pkg.utils.context.get_openai_manager().key_mgr.api_key_fee_threshold)

                        using_key_name = ""
                        for api_key in api_keys:
                            reply_str += "{}:\n - {}美元 {}%\n".format(api_key,
                                                                       round(
                                                                           pkg.utils.context.get_openai_manager().key_mgr.get_fee(
                                                                               api_keys[api_key]), 6),
                                                                       round(
                                                                           pkg.utils.context.get_openai_manager().key_mgr.get_fee(
                                                                               api_keys[
                                                                                   api_key]) / pkg.utils.context.get_openai_manager().key_mgr.api_key_fee_threshold * 100,
                                                                           3))
                            if api_keys[api_key] == pkg.utils.context.get_openai_manager().key_mgr.using_key:
                                using_key_name = api_key
                        reply_str += "\n当前使用:{}".format(using_key_name)

                        reply = [reply_str]

                    elif cmd == 'draw':
                        if len(params) == 0:
                            reply = ["[bot]err:请输入图片描述文字"]
                        else:
                            session = pkg.openai.session.get_session(session_name)

                            res = session.draw_image(" ".join(params))

                            logging.debug("draw_image result:{}".format(res))
                            reply = [Image(url=res['data'][0]['url'])]
                            if not (hasattr(config, 'include_image_description')
                                    and not config.include_image_description):
                                reply.append(" ".join(params))
                    elif cmd == 'reload' and launcher_type == 'person' and launcher_id == config.admin_qq:
                        def reload_task():
                            pkg.utils.reloader.reload_all()

                        threading.Thread(target=reload_task, daemon=True).start()
                    elif cmd == 'update' and launcher_type == 'person' and launcher_id == config.admin_qq:
                        def update_task():
                            try:
                                pkg.utils.updater.update_all()
                            except Exception as e0:
                                pkg.utils.context.get_qqbot_manager().notify_admin("更新失败:{}".format(e0))
                                return
                            pkg.utils.reloader.reload_all(notify=False)
                            pkg.utils.context.get_qqbot_manager().notify_admin("更新完成")

                        threading.Thread(target=update_task, daemon=True).start()
                    else:
                        reply = ["[bot]err:未知的指令或权限不足: "+cmd]
                except Exception as e:
                    mgr.notify_admin("{}指令执行失败:{}".format(session_name, e))
                    logging.exception(e)
                    reply = ["[bot]err:{}".format(e)]
            else:  # 消息
                logging.info("[{}]发送消息:{}".format(session_name, text_message[:min(20, len(text_message))] + (
                    "..." if len(text_message) > 20 else "")))

                session = pkg.openai.session.get_session(session_name)

                while True:
                    try:
                        prefix = "[GPT]" if hasattr(config, "show_prefix") and config.show_prefix else ""
                        reply = [prefix + session.append(text_message)]
                    except openai.error.APIConnectionError as e:
                        mgr.notify_admin("{}会话调用API失败:{}".format(session_name, e))
                        reply = ["[bot]err:调用API失败，请重试或联系作者，或等待修复"]
                    except openai.error.RateLimitError as e:
                        # 尝试切换api-key
                        current_tokens_amt = pkg.utils.context.get_openai_manager().key_mgr.get_fee(
                            pkg.utils.context.get_openai_manager().key_mgr.get_using_key())
                        pkg.utils.context.get_openai_manager().key_mgr.set_current_exceeded()
                        switched, name = pkg.utils.context.get_openai_manager().key_mgr.auto_switch()

                        if not switched:
                            mgr.notify_admin("API调用额度超限({}),无可用api_key,请向OpenAI账户充值或在config.py中更换api_key".format(
                                current_tokens_amt))
                            reply = ["[bot]err:API调用额度超额，请联系作者，或等待修复"]
                        else:
                            openai.api_key = pkg.utils.context.get_openai_manager().key_mgr.get_using_key()
                            mgr.notify_admin("API调用额度超限({}),接口报错,已切换到{}".format(current_tokens_amt, name))
                            reply = ["[bot]err:API调用额度超额，已自动切换，请重新发送消息"]
                            continue
                    except openai.error.InvalidRequestError as e:
                        mgr.notify_admin("{}API调用参数错误:{}\n\n这可能是由于config.py中的prompt_submit_length参数或"
                                         "completion_api_params中的max_tokens参数数值过大导致的，请尝试将其降低".format(
                            session_name, e))
                        reply = ["[bot]err:API调用参数错误，请联系作者，或等待修复"]
                    except openai.error.ServiceUnavailableError as e:
                        # mgr.notify_admin("{}API调用服务不可用:{}".format(session_name, e))
                        reply = ["[bot]err:API调用服务暂不可用，请尝试重试"]
                    except Exception as e:
                        logging.exception(e)
                        reply = ["[bot]err:{}".format(e)]
                    break

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
