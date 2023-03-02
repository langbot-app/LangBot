# 指令处理模块
import logging
import json
import datetime
import os
import threading

import pkg.openai.session
import pkg.openai.manager
import pkg.utils.reloader
import pkg.utils.updater
import pkg.utils.context
import pkg.qqbot.message
import pkg.utils.credit as credit

from mirai import Image


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


def plugin_operation(cmd, params, is_admin):
    reply = []

    import pkg.plugin.host as plugin_host
    import pkg.utils.updater as updater

    plugin_list = plugin_host.__plugins__

    if len(params) == 0:
        reply_str = "[bot]所有插件({}):\n".format(len(plugin_host.__plugins__))
        idx = 0
        for key in plugin_host.iter_plugins_name():
            plugin = plugin_list[key]
            reply_str += "\n#{} {} {}\n{}\nv{}\n作者: {}\n"\
                .format((idx+1), plugin['name'],
                        "[已禁用]" if not plugin['enabled'] else "",
                        plugin['description'],
                        plugin['version'], plugin['author'])

            if updater.is_repo("/".join(plugin['path'].split('/')[:-1])):
                remote_url = updater.get_remote_url("/".join(plugin['path'].split('/')[:-1]))
                if remote_url != "https://github.com/RockChinQ/QChatGPT" and remote_url != "https://gitee.com/RockChin/QChatGPT":
                    reply_str += "源码: "+remote_url+"\n"

            idx += 1

        reply = [reply_str]
    elif params[0] == 'update':
        # 更新所有插件
        if is_admin:
            def closure():
                import pkg.utils.context
                updated = []
                for key in plugin_list:
                    plugin = plugin_list[key]
                    if updater.is_repo("/".join(plugin['path'].split('/')[:-1])):
                        success = updater.pull_latest("/".join(plugin['path'].split('/')[:-1]))
                        if success:
                            updated.append(plugin['name'])

                # 检查是否有requirements.txt
                pkg.utils.context.get_qqbot_manager().notify_admin("正在安装依赖...")
                for key in plugin_list:
                    plugin = plugin_list[key]
                    if os.path.exists("/".join(plugin['path'].split('/')[:-1])+"/requirements.txt"):
                        logging.info("{}检测到requirements.txt，安装依赖".format(plugin['name']))
                        import pkg.utils.pkgmgr
                        pkg.utils.pkgmgr.install_requirements("/".join(plugin['path'].split('/')[:-1])+"/requirements.txt")

                        import main
                        main.reset_logging()

                pkg.utils.context.get_qqbot_manager().notify_admin("已更新插件: {}".format(", ".join(updated)))

            threading.Thread(target=closure).start()
            reply = ["[bot]正在更新所有插件，请勿重复发起..."]
        else:
            reply = ["[bot]err:权限不足"]
    elif params[0].startswith("http"):
        if is_admin:

            def closure():
                try:
                    plugin_host.install_plugin(params[0])
                    pkg.utils.context.get_qqbot_manager().notify_admin("插件安装成功，请发送 !reload 指令重载插件")
                except Exception as e:
                    logging.error("插件安装失败:{}".format(e))
                    pkg.utils.context.get_qqbot_manager().notify_admin("插件安装失败:{}".format(e))

            threading.Thread(target=closure, args=()).start()
            reply = ["[bot]正在安装插件..."]
        else:
            reply = ["[bot]err:权限不足，请使用管理员账号私聊发起"]
    return reply


def process_command(session_name: str, text_message: str, mgr, config,
                    launcher_type: str, launcher_id: int, sender_id: int, is_admin: bool) -> list:
    reply = []
    try:
        logging.info(
            "[{}]发起指令:{}".format(session_name, text_message[:min(20, len(text_message))] + (
                "..." if len(text_message) > 20 else "")))

        cmd = text_message[1:].strip().split(' ')[0]

        params = text_message[1:].strip().split(' ')[1:]
        if cmd == 'help':
            reply = ["[bot]" + config.help_message]
        elif cmd == 'reset':
            if len(params) == 0:
                pkg.openai.session.get_session(session_name).reset(explicit=True)
                reply = ["[bot]会话已重置"]
            else:
                pkg.openai.session.get_session(session_name).reset(explicit=True, use_prompt=params[0])
                reply = ["[bot]会话已重置，使用场景预设:{}".format(params[0])]
        elif cmd == 'last':
            result = pkg.openai.session.get_session(session_name).last_session()
            if result is None:
                reply = ["[bot]没有前一次的对话"]
            else:
                datetime_str = datetime.datetime.fromtimestamp(result.create_timestamp).strftime(
                    '%Y-%m-%d %H:%M:%S')
                reply = ["[bot]已切换到前一次的对话：\n创建时间:{}\n".format(datetime_str)]
        elif cmd == 'next':
            result = pkg.openai.session.get_session(session_name).next_session()
            if result is None:
                reply = ["[bot]没有后一次的对话"]
            else:
                datetime_str = datetime.datetime.fromtimestamp(result.create_timestamp).strftime(
                    '%Y-%m-%d %H:%M:%S')
                reply = ["[bot]已切换到后一次的对话：\n创建时间:{}\n".format(datetime_str)]
        elif cmd == 'prompt':
            msgs = ""
            session:list = pkg.openai.session.get_session(session_name).prompt
            for msg in session:
                if len(params) != 0 and params[0] in ['-all', '-a']:
                    msgs = msgs + "{}: {}\n\n".format(msg['role'], msg['content'])
                elif len(msg['content']) > 30:
                    msgs = msgs + "[{}]: {}...\n\n".format(msg['role'], msg['content'][:30])
                else:
                    msgs = msgs + "[{}]: {}\n\n".format(msg['role'], msg['content'])
            reply = ["[bot]当前对话所有内容：\n{}".format(msgs)]
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
                    msg = ""
                    try:
                        msg = json.loads(results[i]['prompt'])
                    except json.decoder.JSONDecodeError:
                        msg = pkg.openai.session.reset_session_prompt(session_name, results[i]['prompt'])
                        # 持久化
                        pkg.openai.session.get_session(session_name).persistence()
                    if len(msg) >= 2:
                        reply_str += "#{} 创建:{} {}\n".format(i + page * 10,
                                                               datetime_obj.strftime("%Y-%m-%d %H:%M:%S"),
                                                               msg[1]['content'])
                    else:
                        reply_str += "#{} 创建:{} {}\n".format(i + page * 10,
                                                               datetime_obj.strftime("%Y-%m-%d %H:%M:%S"),
                                                               "无内容")
                    if results[i]['create_timestamp'] == pkg.openai.session.get_session(
                            session_name).create_timestamp:
                        current = i + page * 10

                reply_str += "\n以上信息倒序排列"
                if current != -1:
                    reply_str += ",当前会话是 #{}\n".format(current)
                else:
                    reply_str += ",当前处于全新会话或不在此页"

                reply = [reply_str]
        elif cmd == 'resend':
            session = pkg.openai.session.get_session(session_name)
            to_send = session.undo()

            reply = pkg.qqbot.message.process_normal_message(to_send, mgr, config,
                                                             launcher_type, launcher_id, sender_id)
        elif cmd == 'usage':
            reply_str = "[bot]各api-key使用情况:\n\n"

            api_keys = pkg.utils.context.get_openai_manager().key_mgr.api_key
            for key_name in api_keys:
                text_length = pkg.utils.context.get_openai_manager().audit_mgr \
                    .get_text_length_of_key(api_keys[key_name])
                image_count = pkg.utils.context.get_openai_manager().audit_mgr \
                    .get_image_count_of_key(api_keys[key_name])
                reply_str += "{}:\n - 文本长度:{}\n - 图片数量:{}\n".format(key_name, int(text_length),
                                                                            int(image_count))
                # 获取此key的额度
                try:
                    credit_data = credit.fetch_credit_data(api_keys[key_name])
                    reply_str += " - 使用额度:{:.2f}/{:.2f}\n".format(credit_data['total_used'],credit_data['total_granted'])
                except Exception as e:
                    logging.warning("获取额度失败:{}".format(e))

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

        elif cmd == 'plugin':
            reply = plugin_operation(cmd, params, is_admin)

        elif cmd == 'default':
            if len(params) == 0:
                # 输出目前所有情景预设
                import pkg.openai.dprompt as dprompt
                reply_str = "[bot]当前所有情景预设:\n\n"
                for key,value in dprompt.get_prompt_dict().items():
                    reply_str += "  - {}: {}\n".format(key,value)

                reply_str += "\n当前默认情景预设:{}\n".format(dprompt.get_current())
                reply_str += "请使用!default <情景预设>来设置默认情景预设"
                reply = [reply_str]
            elif len(params) >0  and is_admin:
                # 设置默认情景
                import pkg.openai.dprompt as dprompt
                try:
                    dprompt.set_current(params[0])
                    reply = ["[bot]已设置默认情景预设为:{}".format(dprompt.get_current())]
                except KeyError:
                    reply = ["[bot]err: 未找到情景预设:{}".format(params[0])]
            else:
                reply = ["[bot]err: 仅管理员可设置默认情景预设"]
        elif cmd == 'reload' and is_admin:
            def reload_task():
                pkg.utils.reloader.reload_all()

            threading.Thread(target=reload_task, daemon=True).start()
        elif cmd == 'update' and is_admin:
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
        elif cmd == 'cfg' and is_admin:
            reply = config_operation(cmd, params)
        else:
            if cmd.startswith("~") and is_admin:
                config_item = cmd[1:]
                params = [config_item] + params
                reply = config_operation("cfg", params)
            else:
                reply = ["[bot]err:未知的指令或权限不足: " + cmd]
    except Exception as e:
        mgr.notify_admin("{}指令执行失败:{}".format(session_name, e))
        logging.exception(e)
        reply = ["[bot]err:{}".format(e)]

    return reply
