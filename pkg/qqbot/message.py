# 普通消息处理模块
import logging
import openai
import pkg.utils.context
import pkg.openai.session

import pkg.plugin.host as plugin_host
import pkg.plugin.models as plugin_models
import pkg.qqbot.blob as blob
import tips as tips_custom


def handle_exception(notify_admin: str = "", set_reply: str = "") -> list:
    """处理异常，当notify_admin不为空时，会通知管理员，返回通知用户的消息"""
    import config
    pkg.utils.context.get_qqbot_manager().notify_admin(notify_admin)
    if config.hide_exce_info_to_user:
        return [tips_custom.alter_tip_message] if tips_custom.alter_tip_message else []
    else:
        return [set_reply]


def process_normal_message(text_message: str, mgr, config, launcher_type: str,
                           launcher_id: int, sender_id: int) -> list:
    session_name = f"{launcher_type}_{launcher_id}"
    logging.info("[{}]发送消息:{}".format(session_name, text_message[:min(20, len(text_message))] + (
        "..." if len(text_message) > 20 else "")))

    session = pkg.openai.session.get_session(session_name)

    unexpected_exception_times = 0

    max_unexpected_exception_times = 3

    reply = []
    while True:
        if unexpected_exception_times >= max_unexpected_exception_times:
            reply = handle_exception(notify_admin=f"{session_name}，多次尝试失败。", set_reply=f"[bot]多次尝试失败，请重试或联系管理员")
            break
        try:
            prefix = "[GPT]" if config.show_prefix else ""

            text, finish_reason, funcs = session.query(text_message)

            # 触发插件事件
            args = {
                "launcher_type": launcher_type,
                "launcher_id": launcher_id,
                "sender_id": sender_id,
                "session": session,
                "prefix": prefix,
                "response_text": text,
                "finish_reason": finish_reason,
                "funcs_called": funcs,
            }

            event = pkg.plugin.host.emit(plugin_models.NormalMessageResponded, **args)

            if event.get_return_value("prefix") is not None:
                prefix = event.get_return_value("prefix")

            if event.get_return_value("reply") is not None:
                reply = event.get_return_value("reply")

            if not event.is_prevented_default():
                reply = [prefix + text]

        except openai.error.APIConnectionError as e:
            err_msg = str(e)
            if err_msg.__contains__('Error communicating with OpenAI'):
                reply = handle_exception("{}会话调用API失败:{}\n您的网络无法访问OpenAI接口或网络代理不正常".format(session_name, e),
                                         "[bot]err:调用API失败，请重试或联系管理员，或等待修复")
            else:
                reply = handle_exception("{}会话调用API失败:{}".format(session_name, e), "[bot]err:调用API失败，请重试或联系管理员，或等待修复")
        except openai.error.RateLimitError as e:
            logging.debug(type(e))
            logging.debug(e.error['message'])

            if 'message' in e.error and e.error['message'].__contains__('You exceeded your current quota'):
                # 尝试切换api-key
                current_key_name = pkg.utils.context.get_openai_manager().key_mgr.get_key_name(
                    pkg.utils.context.get_openai_manager().key_mgr.using_key
                )
                pkg.utils.context.get_openai_manager().key_mgr.set_current_exceeded()

                # 触发插件事件
                args = {
                    'key_name': current_key_name,
                    'usage': pkg.utils.context.get_openai_manager().audit_mgr
                            .get_usage(pkg.utils.context.get_openai_manager().key_mgr.get_using_key_md5()),
                    'exceeded_keys': pkg.utils.context.get_openai_manager().key_mgr.exceeded,
                }
                event = plugin_host.emit(plugin_models.KeyExceeded, **args)

                if not event.is_prevented_default():
                    switched, name = pkg.utils.context.get_openai_manager().key_mgr.auto_switch()

                    if not switched:
                        reply = handle_exception(
                            "api-key调用额度超限({}),无可用api_key,请向OpenAI账户充值或在config.py中更换api_key；如果你认为这是误判，请尝试重启程序。".format(
                                current_key_name), "[bot]err:API调用额度超额，请联系管理员，或等待修复")
                    else:
                        openai.api_key = pkg.utils.context.get_openai_manager().key_mgr.get_using_key()
                        mgr.notify_admin("api-key调用额度超限({}),接口报错,已切换到{}".format(current_key_name, name))
                        reply = ["[bot]err:API调用额度超额，已自动切换，请重新发送消息"]
                        continue
            elif 'message' in e.error and e.error['message'].__contains__('You can retry your request'):
                # 重试
                unexpected_exception_times += 1
                continue
            elif 'message' in e.error and e.error['message']\
                    .__contains__('The server had an error while processing your request'):
                # 重试
                unexpected_exception_times += 1
                continue
            else:
                reply = handle_exception("{}会话调用API失败:{}".format(session_name, e),
                                         "[bot]err:RateLimitError,请重试或联系作者，或等待修复")
        except openai.error.InvalidRequestError as e:
            if config.auto_reset and "This model's maximum context length is" in str(e):
                session.reset(persist=True)
                reply = [tips_custom.session_auto_reset_message]
            else:
                reply = handle_exception("{}API调用参数错误:{}\n".format(
                                session_name, e), "[bot]err:API调用参数错误，请联系管理员，或等待修复")
        except openai.error.ServiceUnavailableError as e:
            reply = handle_exception("{}API调用服务不可用:{}".format(session_name, e), "[bot]err:API调用服务不可用，请重试或联系管理员，或等待修复")
        except Exception as e:
            logging.exception(e)
            reply = handle_exception("{}会话处理异常:{}".format(session_name, e), "[bot]err:{}".format(e))
        break

    return reply
