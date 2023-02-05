import logging

import openai

import pkg.openai.keymgr
import pkg.utils.context
import pkg.audit.gatherer


# 为其他模块提供与OpenAI交互的接口
class OpenAIInteract:
    api_params = {}

    key_mgr: pkg.openai.keymgr.KeysManager = None

    audit_mgr: pkg.audit.gatherer.DataGatherer = None

    default_image_api_params = {
        "size": "256x256",
    }

    def __init__(self, api_key: str):
        # self.api_key = api_key

        self.key_mgr = pkg.openai.keymgr.KeysManager(api_key)
        self.audit_mgr = pkg.audit.gatherer.DataGatherer()

        openai.api_key = self.key_mgr.get_using_key()

        pkg.utils.context.set_openai_manager(self)

    # 请求OpenAI Completion
    def request_completion(self, prompt, stop):
        config = pkg.utils.context.get_config()
        response = openai.Completion.create(
            prompt=prompt,
            stop=stop,
            **config.completion_api_params
        )

        logging.debug("OpenAI response: %s", response)

        self.audit_mgr.report_text_model_usage(config.completion_api_params['model'],
                                               response['usage']['total_tokens'])

        return response

    def request_image(self, prompt):

        config = pkg.utils.context.get_config()
        params = config.image_api_params if hasattr(config, "image_api_params") else self.default_image_api_params

        response = openai.Image.create(
            prompt=prompt,
            n=1,
            **params
        )

        self.audit_mgr.report_image_model_usage(params['size'])

        return response

