import openai

openai.api_key = "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"

resp = openai.Completion.create(
    prompt="user:你好，今天天气怎么样？\nbot:",
    model="text-davinci-003",
    temperature=0.9,  # 数值越低得到的回答越理性，取值范围[0, 1]
    top_p=1,  # 生成的文本的文本与要求的符合度, 取值范围[0, 1]
    frequency_penalty=0.2,
    presence_penalty=1.0,
)

print(resp)