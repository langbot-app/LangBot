# 指令处理模块
import logging
import json
import datetime
import os
import threading
import traceback

import pkg.openai.session
import pkg.openai.manager
import pkg.utils.reloader
import pkg.utils.updater
import pkg.utils.context
import pkg.qqbot.message
import pkg.utils.credit as credit
import pkg.qqbot.cmds.model as cmdmodel

from mirai import Image



def process_command(session_name: str, text_message: str, mgr, config,
                    launcher_type: str, launcher_id: int, sender_id: int, is_admin: bool) -> list:
    reply = []
    try:
        logging.info(
            "[{}]发起指令:{}".format(session_name, text_message[:min(20, len(text_message))] + (
                "..." if len(text_message) > 20 else "")))

        cmd = text_message[1:].strip().split(' ')[0]

        params = text_message[1:].strip().split(' ')[1:]

        # 把!~开头的转换成!cfg 
        if cmd.startswith('~'):
            params = [cmd[1:]] + params
            cmd = 'cfg'

        # 选择指令处理函数
        cmd_obj = cmdmodel.search(cmd)
        if cmd_obj is not None and (cmd_obj['admin_only'] is False or is_admin):
            cmd_func = cmd_obj['func']
            reply = cmd_func(
                cmd=cmd,
                params=params,
                session_name=session_name,
                text_message=text_message,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=sender_id,
                is_admin=is_admin,
            )
        else:
            reply = ["[bot]err:未知的指令或权限不足: " + cmd]

        return reply
    except Exception as e:
        mgr.notify_admin("{}指令执行失败:{}".format(session_name, e))
        logging.exception(e)
        reply = ["[bot]err:{}".format(e)]

    return reply
