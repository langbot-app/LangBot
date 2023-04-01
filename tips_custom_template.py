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
help_message = """【可自定义】
此机器人通过调用OpenAI的GPT-3大型语言模型生成回复，不具有情感。
你可以用自然语言与其交流，回复的消息中[GPT]开头的为模型生成的语言，[bot]开头的为程序提示。
了解此项目请找QQ 1010553892 联系作者
请不要用其生成整篇文章或大段代码，因为每次只会向模型提交少部分文字，生成大部分文字会产生偏题、前后矛盾等问题
每次会话最后一次交互后{}分钟后会自动结束，结束后将开启新会话，如需继续前一次会话请发送 !last 重新开启
欢迎到github.com/RockChinQ/QChatGPT 给个star
指令帮助信息请查看: https://github.com/RockChinQ/QChatGPT/wiki/%E5%8A%9F%E8%83%BD%E4%BD%BF%E7%94%A8#%E6%9C%BA%E5%99%A8%E4%BA%BA%E6%8C%87%E4%BB%A4""".format(config.session_expire_time // 60)

# ---原config.py结束--

# QChatGPT/pkg/qqbot/manager.py
# 私聊消息超时提示,line:271
reply_message = ["私聊请求超时"]
# 群聊消息超时提示,line:310
replys_message = ["群聊请求超时"]

# 指令权限不足/无效提示
# QChatGPT/pkg/qqbot/command.py，line:57
# 更改代码
# QChatGPT/pkg/qqbot/cmds/mgr.py
# line:266,279
command_admin_message = "权限不足： "
command_err_message = "指令执行出错："
