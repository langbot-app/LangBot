import logging

import openai

from ..openai import keymgr
from ..utils import context
from ..audit import gatherer
from ..openai import modelmgr
from ..openai.api import model as api_model


class OpenAIInteract:
    """OpenAI 接口封装

    将文字接口和图片接口封装供调用方使用
    """

    key_mgr: keymgr.KeysManager = None

    audit_mgr: gatherer.DataGatherer = None

    default_image_api_params = {
        "size": "256x256",
    }

    client: openai.Client = None

    def __init__(self, api_key: str):

        self.key_mgr = keymgr.KeysManager(api_key)
        self.audit_mgr = gatherer.DataGatherer()

        # logging.info("文字总使用量：%d", self.audit_mgr.get_total_text_length())

        self.client = openai.Client(
            api_key=self.key_mgr.get_using_key(),
            base_url=openai.base_url
        )

        context.set_openai_manager(self)

    def request_completion(self, messages: list):
        """请求补全接口回复=
        """
        # 选择接口请求类
        config = context.get_config_manager().data

        request: api_model.RequestBase

        model: str = config['completion_api_params']['model']

        cp_parmas = config['completion_api_params'].copy()
        del cp_parmas['model']

        request = modelmgr.select_request_cls(self.client, model, messages, cp_parmas)

        # 请求接口
        for resp in request:

            if resp['usage']['total_tokens'] > 0:
                self.audit_mgr.report_text_model_usage(
                    model,
                    resp['usage']['total_tokens']
                )

            yield resp

    def request_image(self, prompt) -> dict:
        """请求图片接口回复

        Parameters:
            prompt (str): 提示语

        Returns:
            dict: 响应
        """
        config = context.get_config_manager().data
        params = config['image_api_params']

        response = openai.Image.create(
            prompt=prompt,
            n=1,
            **params
        )

        self.audit_mgr.report_image_model_usage(params['size'])

        return response

