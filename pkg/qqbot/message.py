# 普通消息处理模块
import logging
import openai
import pkg.utils.context
import pkg.openai.session

import pkg.plugin.host as plugin_host
import pkg.plugin.models as plugin_models


def handle_exception(notify_admin: str = "", set_reply: str = "") -> list:
    """处理异常，当notify_admin不为空时，会通知管理员，返回通知用户的消息"""
    import config
    pkg.utils.context.get_qqbot_manager().notify_admin(notify_admin)
    if hasattr(config, 'hide_exce_info_to_user') and config.hide_exce_info_to_user:
        if hasattr(config, 'alter_tip_message'):
            return [config.alter_tip_message] if config.alter_tip_message else []
        else:
            return ["[bot]出错了，请重试或联系管理员"]
    else:
        return [set_reply]


def process_normal_message(text_message: str, mgr, config, launcher_type: str,
                           launcher_id: int, sender_id: int) -> list:
    session_name = f"{launcher_type}_{launcher_id}"
    logging.info("[{}]发送消息:{}".format(session_name, text_message[:min(20, len(text_message))] + (
        "..." if len(text_message) > 20 else "")))

    session = pkg.openai.session.get_session(session_name)

    reply = []
    while True:
        try:
            prefix = "[GPT]" if hasattr(config, "show_prefix") and config.show_prefix else ""

            text = session.append(text_message)

            # 触发插件事件
            args = {
                "launcher_type": launcher_type,
                "launcher_id": launcher_id,
                "sender_id": sender_id,
                "session": session,
                "prefix": prefix,
                "response_text": text
            }

            event = pkg.plugin.host.emit(plugin_models.NormalMessageResponded, **args)

            if event.get_return_value("prefix") is not None:
                prefix = event.get_return_value("prefix")

            if event.get_return_value("reply") is not None:
                reply = event.get_return_value("reply")

            if not event.is_prevented_default():
                reply = [prefix + text]
        except openai.error.APIConnectionError as e:
            reply = handle_exception("{}会话调用API失败:{}".format(session_name, e), "[bot]err:调用API失败，请重试或联系作者，或等待修复")
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
                            "api-key调用额度超限({}),无可用api_key,请向OpenAI账户充值或在config.py中更换api_key".format(
                                current_key_name), "[bot]err:API调用额度超额，请联系作者，或等待修复")
                    else:
                        openai.api_key = pkg.utils.context.get_openai_manager().key_mgr.get_using_key()
                        mgr.notify_admin("api-key调用额度超限({}),接口报错,已切换到{}".format(current_key_name, name))
                        reply = ["[bot]err:API调用额度超额，已自动切换，请重新发送消息"]
                        continue
            elif 'message' in e.error and e.error['message'].__contains__('You can retry your request'):
                # 重试
                continue
            else:
                reply = handle_exception("{}会话调用API失败:{}".format(session_name, e),
                                         "[bot]err:RateLimitError,请重试或联系作者，或等待修复")
        except openai.error.InvalidRequestError as e:
            reply = handle_exception("{}API调用参数错误:{}\n\n这可能是由于config.py中的prompt_submit_length参数或"
                             "completion_api_params中的max_tokens参数数值过大导致的，请尝试将其降低".format(
                             session_name, e), "[bot]err:API调用参数错误，请联系作者，或等待修复")
        except openai.error.ServiceUnavailableError as e:
            reply = handle_exception("{}API调用服务不可用:{}".format(session_name, e), "[bot]err:API调用服务不可用，请重试或联系作者，或等待修复")
        except Exception as e:
            logging.exception(e)
            reply = handle_exception("{}会话处理异常:{}".format(session_name, e), "[bot]err:{}".format(e))
        break

    return reply
