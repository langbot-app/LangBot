import logging

# Mirai的配置
# 请到配置mirai的步骤中的教程查看每个字段的信息
# host: 运行mirai的主机地址
# port: 运行mirai的主机端口
# verifyKey: mirai-api-http的verifyKey
# qq: 机器人的QQ号
mirai_http_api_config = {
    "host": "",
    "port": 8080,
    "verifyKey": "",
    "qq": 0
}

# MySQL数据库的配置
# host: 数据库地址
# port: 数据库端口
# user: 数据库用户名
# password: 数据库密码
# database: 数据库名
mysql_config = {
    "host": "",
    "port": 3306,
    "user": "",
    "password": "",
    "database": ""
}

# OpenAI的配置
# api_key: OpenAI的API Key
openai_config = {
    "api_key": "",
}

# OpenAI的completion API的参数
# 不了解的话请不要修改，具体请查看OpenAI的文档
completion_api_params = {
    "model": "text-davinci-003",
    "temperature": 0.8,
    "max_tokens": 200,  # 每次向OpenAI请求的最大字符数
    "top_p": 1,
    "frequency_penalty": 0.2,
    "presence_penalty": 0.4,
}

# 每次向OpenAI接口发送对话记录上下文的字符数
# 最大不超过(4096 - max_tokens)个字符，max_tokens为上述completion_api_params中的max_tokens
# 注意：较大的prompt_submit_length会导致OpenAI账户额度消耗更快
prompt_submit_length = 1024

# 每次向OpenAI接口发送对话记录上下文的聊天回合数
# 不建议过大，向OpenAI接口发送对话上下文时保证内容不超过prompt_submit_length个字符，
# 不超过prompt_submit_round_amount个回合
prompt_submit_round_amount = 8

# 消息处理的超时时间，单位为秒
process_message_timeout = 20

# 消息处理超时重试次数
retry_times = 3

# 每个会话的过期时间，单位为秒
# 默认值20分钟
session_expire_time = 60 * 20

# 日志级别
logging_level = logging.INFO

# 管理员QQ号，用于接收报错等通知
admin_qq = 0

# 定制帮助消息
help_message = """此机器人通过调用OpenAI的GPT-3大型语言模型生成回复，不具有情感。
你可以用自然语言与其交流，回复的消息中[GPT]开头的为模型生成的语言，[bot]开头的为程序提示。
了解此项目请找QQ 1010553892 联系作者
请不要用其生成整篇文章或大段代码，因为每次只会向模型提交少部分文字，生成大部分文字会产生偏题、前后矛盾等问题
每次会话最后一次交互后{}分钟后会自动结束，结束后将开启新会话，如需继续前一次会话请发送 !last 重新开启
欢迎到github.com/RockChinQ/QChatGPT 给个star

帮助信息：
!help - 显示帮助
!reset - 重置会话
!last - 切换到前一次的对话
!next - 切换到后一次的对话
!prompt - 显示当前对话所有内容
!list - 列出所有历史会话""".format(session_expire_time // 60)
