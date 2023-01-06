# 此模块提供了消息处理的具体逻辑的接口
import asyncio
import datetime
import json
import threading

from func_timeout import func_set_timeout
import logging
import openai

from mirai import Image, MessageChain

# 这里不使用动态引入config
# 因为在这里动态引入会卡死程序
# 而此模块静态引用config与动态引入的表现一致
import config as config_init_import

import pkg.openai.session
import pkg.openai.manager
import pkg.utils.reloader
import pkg.utils.updater
import pkg.utils.context

processing = []


def config_operation(cmd, params):
    reply = []
    config = pkg.utils.context.get_config()
    reply_str = ""
    if len(params) == 0:
        reply = ["[bot]err:请输入配置项"]
    else:
        cfg_name = params[0]
        if cfg_name == 'all':
            reply_str = "[bot]所有配置项:\n\n"
            for cfg in dir(config):
                if not cfg.startswith('__') and not cfg == 'logging':
                    # 根据配置项类型进行格式化，如果是字典则转换为json并格式化
                    if isinstance(getattr(config, cfg), str):
                        reply_str += "{}: \"{}\"\n".format(cfg, getattr(config, cfg))
                    elif isinstance(getattr(config, cfg), dict):
                        # 不进行unicode转义，并格式化
                        reply_str += "{}: {}\n".format(cfg,
                                                       json.dumps(getattr(config, cfg),
                                                                  ensure_ascii=False, indent=4))
                    else:
                        reply_str += "{}: {}\n".format(cfg, getattr(config, cfg))
            reply = [reply_str]
        elif cfg_name in dir(config):
            if len(params) == 1:
                # 按照配置项类型进行格式化
                if isinstance(getattr(config, cfg_name), str):
                    reply_str = "[bot]配置项{}: \"{}\"\n".format(cfg_name, getattr(config, cfg_name))
                elif isinstance(getattr(config, cfg_name), dict):
                    reply_str = "[bot]配置项{}: {}\n".format(cfg_name,
                                                             json.dumps(getattr(config, cfg_name),
                                                                        ensure_ascii=False, indent=4))
                else:
                    reply_str = "[bot]配置项{}: {}\n".format(cfg_name, getattr(config, cfg_name))
                reply = [reply_str]
            else:
                cfg_value = " ".join(params[1:])
                # 类型转换，如果是json则转换为字典
                if cfg_value == 'true':
                    cfg_value = True
                elif cfg_value == 'false':
                    cfg_value = False
                elif cfg_value.isdigit():
                    cfg_value = int(cfg_value)
                elif cfg_value.startswith('{') and cfg_value.endswith('}'):
                    cfg_value = json.loads(cfg_value)
                else:
                    try:
                        cfg_value = float(cfg_value)
                    except ValueError:
                        pass

                # 检查类型是否匹配
                if isinstance(getattr(config, cfg_name), type(cfg_value)):
                    setattr(config, cfg_name, cfg_value)
                    pkg.utils.context.set_config(config)
                    reply = ["[bot]配置项{}修改成功".format(cfg_name)]
                else:
                    reply = ["[bot]err:配置项{}类型不匹配".format(cfg_name)]

        else:
            reply = ["[bot]err:未找到配置项 {}".format(cfg_name)]

    return reply


@func_set_timeout(config_init_import.process_message_timeout)
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

        config = pkg.utils.context.get_config()

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
                    elif cmd == 'fee':
                        api_keys = pkg.utils.context.get_openai_manager().key_mgr.api_key
                        reply_str = "[bot]api-key费用情况(估算):(阈值:{})\n\n".format(
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
                    elif cmd == 'usage':
                        reply_str = "[bot]各api-key使用情况:\n\n"

                        api_keys = pkg.utils.context.get_openai_manager().key_mgr.api_key
                        for key_name in api_keys:
                            text_length = pkg.utils.context.get_openai_manager().audit_mgr\
                                .get_text_length_of_key(api_keys[key_name])
                            image_count = pkg.utils.context.get_openai_manager().audit_mgr\
                                .get_image_count_of_key(api_keys[key_name])
                            reply_str += "{}:\n - 文本长度:{}\n - 图片数量:{}\n".format(key_name, int(text_length), int(image_count))

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
                    elif cmd == 'version':
                        reply_str = "[bot]当前版本:\n{}\n".format(pkg.utils.updater.get_current_version_info())
                        try:
                            if pkg.utils.updater.is_new_version_available():
                                reply_str += "\n有新版本可用，请使用命令 !update 进行更新"
                        except:
                            pass

                        reply = [reply_str]
                    elif cmd == 'reload' and launcher_type == 'person' and launcher_id == config.admin_qq:
                        def reload_task():
                            pkg.utils.reloader.reload_all()

                        threading.Thread(target=reload_task, daemon=True).start()
                    elif cmd == 'update' and launcher_type == 'person' and launcher_id == config.admin_qq:
                        def update_task():
                            try:
                                if pkg.utils.updater.update_all():
                                    pkg.utils.reloader.reload_all(notify=False)
                                    pkg.utils.context.get_qqbot_manager().notify_admin("更新完成")
                                else:
                                    pkg.utils.context.get_qqbot_manager().notify_admin("无新版本")
                            except Exception as e0:
                                pkg.utils.context.get_qqbot_manager().notify_admin("更新失败:{}".format(e0))
                                return

                        threading.Thread(target=update_task, daemon=True).start()

                        reply = ["[bot]正在更新，请耐心等待，请勿重复发起更新..."]
                    elif cmd == 'cfg' and launcher_type == 'person' and launcher_id == config.admin_qq:
                        reply = config_operation(cmd, params)
                    else:
                        if cmd.startswith("~") and launcher_type == 'person' and launcher_id == config.admin_qq:
                            config_item = cmd[1:]
                            params = [config_item] + params
                            reply = config_operation("cfg", params)
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
