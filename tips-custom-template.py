import config

# ---------------------------------------------花里胡哨参数---------------------------------------------
# ---原config.py开始--

# 消息处理出错时向用户发送的提示信息，仅当hide_exce_info_to_user为True时生效
# 设置为空字符串时，不发送提示信息
# config.py,line:232
# pkg/qqbot/message.py,line:19
alter_tip_message = '出错了，请稍后再试'

# drop策略时，超过限速均值时，丢弃的对话的提示信息，仅当rate_limitation_strategy为"drop"时生效
# 若设置为空字符串，则不发送提示信息
# config.py,line:265
# pkg/qqbot/process.py,line:122
rate_limit_drop_tip = "本分钟对话次数超过限速次数，此对话被丢弃"

# 指令！help帮助消息
# config.py,line:279
# pkg/qqbot/process.py,line:122
help_message = """此机器人通过调用大型语言模型生成回复，不具有情感。
你可以用自然语言与其交流，回复的消息中[GPT]开头的为模型生成的语言，[bot]开头的为程序提示。
欢迎到github.com/RockChinQ/QChatGPT 给个star"""

# ---原config.py结束--

# QChatGPT/pkg/qqbot/manager.py
# 私聊消息超时提示,line:271
reply_message = "私聊请求超时"
# 群聊消息超时提示,line:310
replys_message = "群聊请求超时"

# 指令权限不足/无效提示
# QChatGPT/pkg/qqbot/command.py，line:57
# 更改代码
# QChatGPT/pkg/qqbot/cmds/mgr.py
# line:266,279
command_admin_message = "权限不足： "
command_err_message = "指令执行出错："

# 会话重置提示
# pkg/qqbot/cmds/session/reset.py，line:25,31
command_reset_message = "[bot]会话已重置"
command_reset_name_message = "[bot]会话已重置，使用场景预设:"
