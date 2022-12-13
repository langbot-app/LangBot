import openai

import config

inst = None


# 为其他模块提供与OpenAI交互的接口
class OpenAIInteract:
    api_key = ''
    api_params = {}

    def __init__(self, api_key: str, api_params: dict):
        self.api_key = api_key
        self.api_params = api_params

        openai.api_key = self.api_key

        global inst
        inst = self

    # 请求OpenAI Completion
    def request_completion(self, prompt, stop):
        response = openai.Completion.create(
            prompt=prompt,
            stop=stop,
            timeout=config.process_message_timeout,
            **self.api_params
        )
        return response


def get_inst() -> OpenAIInteract:
    global inst
    return inst
