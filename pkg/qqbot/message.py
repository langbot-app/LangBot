# 普通消息处理模块
import logging
import openai
import pkg.utils.context
import pkg.openai.session


def process_normal_message(text_message: str, mgr, config, launcher_type: str, launcher_id: int) -> list:
    session_name = f"{launcher_type}_{launcher_id}"
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
            logging.debug(type(e))
            # 尝试切换api-key
            current_key_name = pkg.utils.context.get_openai_manager().key_mgr.get_key_name(
                pkg.utils.context.get_openai_manager().key_mgr.using_key
            )
            pkg.utils.context.get_openai_manager().key_mgr.set_current_exceeded()
            switched, name = pkg.utils.context.get_openai_manager().key_mgr.auto_switch()

            if not switched:
                mgr.notify_admin(
                    "api-key调用额度超限({}),无可用api_key,请向OpenAI账户充值或在config.py中更换api_key".format(
                        current_key_name))
                reply = ["[bot]err:API调用额度超额，请联系作者，或等待修复"]
            else:
                openai.api_key = pkg.utils.context.get_openai_manager().key_mgr.get_using_key()
                mgr.notify_admin("api-key调用额度超限({}),接口报错,已切换到{}".format(current_key_name, name))
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

    return reply