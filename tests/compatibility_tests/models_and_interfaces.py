import openai
import time

# 测试completion api
models = [
    'gpt-3.5-turbo',
    'gpt-3.5-turbo-0301',
    'text-davinci-003',
    'text-davinci-002',
    'code-davinci-002',
    'code-cushman-001',
    'text-curie-001',
    'text-babbage-001',
    'text-ada-001',
]

openai.api_key = "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"

for model in models:
    print('Testing model: ', model)

    # completion api
    try:
        response = openai.Completion.create(
                        model=model,
                        prompt="Say this is a test",
                        max_tokens=7,
                        temperature=0
                    )
        print('    completion api: ', response['choices'][0]['text'].strip())
    except Exception as e:
        print('    completion api err: ', e)

    # chat completion api
    try:
        completion = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "user", "content": "Hello!"}
                        ]
                    )
        print("    chat api: ",completion.choices[0].message['content'].strip())
    except Exception as e:
        print('    chat api err: ', e)

    time.sleep(60)
