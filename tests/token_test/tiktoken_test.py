import tiktoken
import openai
import json
import os


openai.api_key = os.getenv("OPENAI_API_KEY")


def encode(text: str, model: str):
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    assert enc.decode(enc.encode("hello world")) == "hello world"

    # To get the tokeniser corresponding to a specific model in the OpenAI API:
    enc = tiktoken.encoding_for_model(model)

    return enc.encode(text)


# def ask(prompt: str, model: str = "gpt-3.5-turbo"):
#     # To get the tokeniser corresponding to a specific model in the OpenAI API:
#     enc = tiktoken.encoding_for_model(model)
    
#     resp = openai.ChatCompletion.create(
#         model=model,
#         messages=[
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ]
#     )

#     return enc.encode(prompt), enc.encode(resp['choices'][0]['message']['content']), resp

def ask(
    messages: list,
    model: str = "gpt-3.5-turbo"
):
    enc = tiktoken.encoding_for_model(model)

    resp = openai.ChatCompletion.create(
        model=model,
        messages=messages
    )

    txt = ""

    for r in messages:
        txt += r['role'] + r['content'] + "\n"
    
    txt += "assistant: "

    return enc.encode(txt), enc.encode(resp['choices'][0]['message']['content']), resp


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613"):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

messages = [
    {
        "role": "user",
        "content": "你叫什么名字？"
    },{
        "role": "assistant",
        "content": "我是AI助手，没有具体的名字。你可以叫我GPT-3。有什么可以帮到你的吗？"
    },{
        "role": "user",
        "content": "你是由谁开发的？"
    },{
        "role": "assistant",
        "content": "我是由OpenAI开发的，一家人工智能研究实验室。OpenAI的使命是促进人工智能的发展，使其为全人类带来积极影响。我是由OpenAI团队使用GPT-3模型训练而成的。"
    },{
        "role": "user",
        "content": "很高兴见到你。"
    }
]


pro, rep, resp=ask(messages)

print(len(pro), len(rep))
print(resp)
print(resp['choices'][0]['message']['content'])

print(num_tokens_from_messages(messages, model="gpt-3.5-turbo"))