import logging

import openai

import pkg.openai.keymgr
import pkg.utils.context
import pkg.audit.gatherer
from pkg.openai.modelmgr import select_request_cls

from pkg.openai.api.model import RequestBase


class OpenAIInteract:
    """OpenAI 接口封装

    将文字接口和图片接口封装供调用方使用
    """

    key_mgr: pkg.openai.keymgr.KeysManager = None

    audit_mgr: pkg.audit.gatherer.DataGatherer = None

    default_image_api_params = {
        "size": "256x256",
    }

    def __init__(self, api_key: str):

        self.key_mgr = pkg.openai.keymgr.KeysManager(api_key)
        self.audit_mgr = pkg.audit.gatherer.DataGatherer()

        logging.info("文字总使用量：%d", self.audit_mgr.get_total_text_length())

        openai.api_key = self.key_mgr.get_using_key()

        pkg.utils.context.set_openai_manager(self)

    def request_completion(self, messages: list):
        """请求补全接口回复=
        """
        # 选择接口请求类
        config = pkg.utils.context.get_config()

        request: RequestBase

        model: str = config.completion_api_params['model']

        cp_parmas = config.completion_api_params.copy()
        del cp_parmas['model']

        request = select_request_cls(model, messages, cp_parmas)

        # 请求接口
        for resp in request:
            yield resp

    # 请求OpenAI Completion
    # def request_completion(self, prompts):
    #     """请求补全接口回复
    #     """

    #     config = pkg.utils.context.get_config()

    #     # 根据模型选择使用的接口
    #     ai: ModelRequest = create_openai_model_request(
    #         config.completion_api_params['model'],
    #         'user',
    #         config.openai_config["http_proxy"] if "http_proxy" in config.openai_config else None
    #     )
    #     ai.request(
    #         prompts,
    #         **config.completion_api_params
    #     )
    #     response = ai.get_response()

    #     logging.debug("OpenAI response: %s", response)

    #     # 记录使用量
    #     current_round_token = 0
    #     if 'model' in config.completion_api_params:
    #         self.audit_mgr.report_text_model_usage(config.completion_api_params['model'],
    #                                                ai.get_total_tokens())
    #         current_round_token = ai.get_total_tokens()
    #     elif 'engine' in config.completion_api_params:
    #         self.audit_mgr.report_text_model_usage(config.completion_api_params['engine'],
    #                                                response['usage']['total_tokens'])
    #         current_round_token = response['usage']['total_tokens']

    #     return ai.get_message(), current_round_token

    def request_image(self, prompt) -> dict:
        """请求图片接口回复

        Parameters:
            prompt (str): 提示语

        Returns:
            dict: 响应
        """
        config = pkg.utils.context.get_config()
        params = config.image_api_params

        response = openai.Image.create(
            prompt=prompt,
            n=1,
            **params
        )

        self.audit_mgr.report_image_model_usage(params['size'])

        return response

