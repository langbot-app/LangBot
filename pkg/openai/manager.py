import logging

import openai

import config

import pkg.openai.keymgr

inst = None


# 为其他模块提供与OpenAI交互的接口
class OpenAIInteract:
    api_params = {}

    key_mgr = None

    def __init__(self, api_key: str, api_params: dict):
        # self.api_key = api_key
        self.api_params = api_params

        self.key_mgr = pkg.openai.keymgr.KeysManager(api_key)

        openai.api_key = self.key_mgr.get_using_key()

        global inst
        inst = self

    # 请求OpenAI Completion
    def request_completion(self, prompt, stop):
        logging.debug("请求OpenAI Completion, key:"+openai.api_key)
        response = openai.Completion.create(
            prompt=prompt,
            stop=stop,
            timeout=config.process_message_timeout,
            **self.api_params
        )
        switched = self.key_mgr.report_usage(prompt + response['choices'][0]['text'])
        if switched:
            openai.api_key = self.key_mgr.get_using_key()

        return response


def get_inst() -> OpenAIInteract:
    global inst
    return inst
