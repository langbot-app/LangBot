# 会话管理相关指令
import datetime
import json

from pkg.qqbot.cmds.model import command
import pkg.openai.session
import pkg.utils.context
import config

@command(
    "reset",
    "重置当前会话",
    "!reset\n!reset [使用情景预设名称]",
    [],
    False
)
def cmd_reset(cmd: str, params: list, session_name: str, 
              text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """重置会话"""
    reply = []
    
    if len(params) == 0:
        pkg.openai.session.get_session(session_name).reset(explicit=True)
        reply = ["[bot]会话已重置"]
    else:
        pkg.openai.session.get_session(session_name).reset(explicit=True, use_prompt=params[0])
        reply = ["[bot]会话已重置，使用场景预设:{}".format(params[0])]
    
    return reply


@command(
    "last",
    "切换到前一次会话",
    "!last",
    [],
    False
)
def cmd_last(cmd: str, params: list, session_name: str, 
             text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """切换到前一次会话"""
    reply = []
    result = pkg.openai.session.get_session(session_name).last_session()
    if result is None:
        reply = ["[bot]没有前一次的对话"]
    else:
        datetime_str = datetime.datetime.fromtimestamp(result.create_timestamp).strftime(
            '%Y-%m-%d %H:%M:%S')
        reply = ["[bot]已切换到前一次的对话：\n创建时间:{}\n".format(datetime_str)]

    return reply

@command(
    "next",
    "切换到后一次会话",
    "!next",
    [],
    False
)
def cmd_next(cmd: str, params: list, session_name: str, 
             text_message: str, launcher_type: int, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """切换到后一次会话"""
    reply = []
    
    result = pkg.openai.session.get_session(session_name).next_session()
    if result is None:
        reply = ["[bot]没有后一次的对话"]
    else:
        datetime_str = datetime.datetime.fromtimestamp(result.create_timestamp).strftime(
            '%Y-%m-%d %H:%M:%S')
        reply = ["[bot]已切换到后一次的对话：\n创建时间:{}\n".format(datetime_str)]

    return reply


@command(
    "prompt",
    "获取当前会话的前文",
    "!prompt",
    [],
    False
)
def cmd_prompt(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """获取当前会话的前文"""
    reply = []
     
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

    return reply


@command(
    "list",
    "列出当前会话的所有历史记录",
    "!list\n!list [页数]",
    [],
    False
)
def cmd_list(cmd: str, params: list, session_name: str,
              text_message: str, launcher_type: str, launcher_id: int,
               sender_id: int, is_admin: bool) -> list:
    """列出当前会话的所有历史记录"""
    reply = []
    
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
                                                        msg[0]['content'])
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

    return reply


@command(
    "resend",
    "重新获取上一次问题的回复",
    "!resend",
    [],
    False
)
def cmd_resend(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """重新获取上一次问题的回复"""
    reply = []
    
    session = pkg.openai.session.get_session(session_name)
    to_send = session.undo()

    mgr = pkg.utils.context.get_qqbot_manager()

    reply = pkg.qqbot.message.process_normal_message(to_send, mgr, config,
                                                        launcher_type, launcher_id, sender_id)
    
    return reply


@command(
    "del",
    "删除当前会话的历史记录",
    "!del <序号>\n!del all",
    [],
    False
)
def cmd_del(cmd: str, params: list, session_name: str,
             text_message: str, launcher_type: str, launcher_id: int,
              sender_id: int, is_admin: bool) -> list:
    """删除当前会话的历史记录"""
    reply = []
    
    if len(params) == 0:
        reply = ["[bot]参数不足, 格式: !del <序号>\n可以通过!list查看序号"]
    else:
        if params[0] == 'all':
            pkg.openai.session.get_session(session_name).delete_all_history()
            reply = ["[bot]已删除所有历史会话"]
        elif params[0].isdigit():
            if pkg.openai.session.get_session(session_name).delete_history(int(params[0])):
                reply = ["[bot]已删除历史会话 #{}".format(params[0])]
            else:
                reply = ["[bot]没有历史会话 #{}".format(params[0])]
        else:
            reply = ["[bot]参数错误, 格式: !del <序号>\n可以通过!list查看序号"]
    return reply


@command(
    "default",
    "操作情景预设",
    "!default\n!default [指定情景预设为默认]",
    [],
    False
)
def cmd_default(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """操作情景预设"""
    reply = []

    if len(params) == 0:
        # 输出目前所有情景预设
        import pkg.openai.dprompt as dprompt
        reply_str = "[bot]当前所有情景预设:\n\n"
        for key, value in dprompt.get_prompt_dict().items():
            reply_str += "  - {}: {}\n".format(key, value)

        reply_str += "\n当前默认情景预设:{}\n".format(dprompt.get_current())
        reply_str += "请使用!default <情景预设>来设置默认情景预设"
        reply = [reply_str]
    elif len(params) > 0 and is_admin:
        # 设置默认情景
        import pkg.openai.dprompt as dprompt
        try:
            dprompt.set_current(params[0])
            reply = ["[bot]已设置默认情景预设为:{}".format(dprompt.get_current())]
        except KeyError:
            reply = ["[bot]err: 未找到情景预设:{}".format(params[0])]
    else:
        reply = ["[bot]err: 仅管理员可设置默认情景预设"]

    return reply


@command(
    "delhst",
    "删除指定会话的所有历史记录",
    "!delhst <会话名称>\n!delhst all",
    [],
    True
)
def cmd_delhst(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """删除指定会话的所有历史记录"""
    reply = []
    
    if len(params) == 0:
        reply = ["[bot]err:请输入要删除的会话名: group_<群号> 或者 person_<QQ号>, 或使用 !delhst all 删除所有会话的历史记录"]
    else:
        if params[0] == "all":
            pkg.utils.context.get_database_manager().delete_all_session_history()
            reply = ["[bot]已删除所有会话的历史记录"]
        else:
            if pkg.utils.context.get_database_manager().delete_all_history(params[0]):
                reply = ["[bot]已删除会话 {} 的所有历史记录".format(params[0])]
            else:
                reply = ["[bot]未找到会话 {} 的历史记录".format(params[0])]

    return reply
