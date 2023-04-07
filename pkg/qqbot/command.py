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
# import pkg.qqbot.cmds.model as cmdmodel
import pkg.qqbot.cmds.aamgr as cmdmgr

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

        # 包装参数
        context = cmdmgr.Context(
            command=cmd,
            crt_command=cmd,
            params=params,
            crt_params=params[:],
            session_name=session_name,
            text_message=text_message,
            launcher_type=launcher_type,
            launcher_id=launcher_id,
            sender_id=sender_id,
            is_admin=is_admin,
            privilege=2 if is_admin else 1,  # 普通用户1，管理员2
        )
        try:
            reply = cmdmgr.execute(context)
        except cmdmgr.CommandPrivilegeError as e:
            reply = ["{}".format(e)]

        return reply
    except Exception as e:
        mgr.notify_admin("{}指令执行失败:{}".format(session_name, e))
        logging.exception(e)
        reply = ["[bot]err:{}".format(e)]

    return reply
