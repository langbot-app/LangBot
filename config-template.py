# 配置文件: 注释里标[必需]的参数必须修改, 其他参数根据需要修改, 但请勿删除
import logging

# [必需] Mirai的配置
# 请到配置mirai的步骤中的教程查看每个字段的信息
# host: 运行mirai的主机地址
# port: 运行mirai的主机端口
# verifyKey: mirai-api-http的verifyKey
# qq: 机器人的QQ号
mirai_http_api_config = {
    "host": "localhost",
    "port": 8080,
    "verifyKey": "yirimirai",
    "qq": 1234567890
}

# [必需] OpenAI的配置
# api_key: OpenAI的API Key
# 若只有一个api-key，请直接修改以下内容中的"openai_api_key"为你的api-key
# 如准备了多个api-key，可以以字典的形式填写，程序会自动选择可用的api-key
# 例如{
#       "api0": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
#       "api1": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
#     }
openai_config = {
    "api_key": {
        "default": "openai_api_key"
    },
}

# 单个api-key的使用量警告阈值
# 当使用此api-key进行请求的文字量达到此阈值时，会在控制台输出警告并通知管理员
# 若之后还有未使用超过此值的api-key，则会切换到新的api-key进行请求
api_key_usage_threshold = 900000

# 管理员QQ号，用于接收报错等通知，为0时不发送通知
admin_qq = 0

# 回复消息时是否显示[GPT]前缀
show_prefix = False

# 敏感词过滤开关，以同样数量的*代替敏感词回复
# 请在sensitive.json中添加敏感词
sensitive_word_filter = True

# 每个会话的预设信息，影响所有会话，无视指令重置
# 可以通过这个字段指定某些情况的回复，可直接用自然语言描述指令
# 例如: 如果我之后想获取帮助，请你说“输入!help获取帮助”，
#   这样用户在不知所措的时候机器人就会提示其输入!help获取帮助
# 可参考 https://github.com/PlexPt/awesome-chatgpt-prompts-zh
default_prompt = "如果我之后想获取帮助，请你说“输入!help获取帮助”"

# OpenAI的completion API的参数
# 具体请查看OpenAI的文档
completion_api_params = {
    "model": "text-davinci-003",
    "temperature": 0.6,  # 数值越低得到的回答越理性，取值范围[0, 1]
    "max_tokens": 512,  # 每次向OpenAI请求的最大字符数, 不高于4096
    "top_p": 1,  # 生成的文本的文本与要求的符合度, 取值范围[0, 1]
    "frequency_penalty": 0.2,
    "presence_penalty": 0.4,
}

# 每次向OpenAI接口发送对话记录上下文的字符数
# 最大不超过(4096 - max_tokens)个字符，max_tokens为上述completion_api_params中的max_tokens
# 注意：较大的prompt_submit_length会导致OpenAI账户额度消耗更快
prompt_submit_length = 1536

# 每次向OpenAI接口发送对话记录上下文的聊天回合数
# 不建议过大，向OpenAI接口发送对话上下文时保证内容不超过prompt_submit_length个字符，
# 不超过prompt_submit_round_amount个回合
prompt_submit_round_amount = 16

# 消息处理的超时时间，单位为秒
process_message_timeout = 15

# 消息处理超时重试次数
retry_times = 3

# 每个会话的过期时间，单位为秒
# 默认值20分钟
session_expire_time = 60 * 20

# 日志级别
logging_level = logging.INFO

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
!list - 列出所有历史会话
!usage - 列出各个api-key的使用量""".format(session_expire_time // 60)
