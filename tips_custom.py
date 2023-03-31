import config

# ---------------------------------------------花里胡哨参数---------------------------------------------
# ---原config.py开始--

# 消息处理出错时向用户发送的提示信息，仅当hide_exce_info_to_user为True时生效
# 设置为空字符串时，不发送提示信息
# config.py,line:232
# pkg/qqbot/message.py,line:19
alter_tip_message = '天空一声巨响，魔法少女闪亮登场，唉呀脚滑了，疼~等会再来~（这是一条全世界最人见人爱花见花开玉树临风英俊潇洒美丽且可爱的出错提醒哦~）'

# drop策略时，超过限速均值时，丢弃的对话的提示信息，仅当rate_limitation_strategy为"drop"时生效
# 若设置为空字符串，则不发送提示信息
# config.py,line:265
# pkg/qqbot/process.py,line:122
rate_limit_drop_tip = "欧尼酱慢点我跟不上"

# 指令！help帮助消息
# config.py,line:279
# pkg/qqbot/process.py,line:122
help_message = """
这是一个很正经的帮助文档
此处省略10086字...
biu~biu~biu~""".format(config.session_expire_time // 60)

# ---原config.py结束--

# QChatGPT/pkg/qqbot/manager.py
# 私聊消息超时提示,line:271
reply_message = "天空一声巨响，魔法少女闪亮登场，哎呀脚滑了，疼~(这是一条全世界最人见人爱花见花开玉树临风英俊潇洒美丽且可爱的超时提醒哦。)"
# 群聊消息超时提示,line:310
replys_message = "天空一声巨响，魔法少女闪亮登场，哎呀脚滑了，疼~(这是一条全世界最人见人爱花见花开玉树临风英俊潇洒美丽且可爱的超时提醒哦。)"

# 指令权限不足/无效提示
# QChatGPT/pkg/qqbot/command.py，line:57
# 更改代码
# reply = [format(e)]
# QChatGPT/pkg/qqbot/cmds/mgr.py
# line:266,279
command_admin_message = "你居然想偷看我裙底？坏蛋，大坏蛋，超级大坏蛋，无敌超级大坏蛋，宇宙无敌超级大坏蛋。哼! "
command_err_message = "你又再想涩涩的事了？"
