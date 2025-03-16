from __future__ import annotations

import aiohttp

from . import entities, requester
from ...core import app
from ...discover import engine
from . import token
from ...entity.persistence import model
from .requesters import bailianchatcmpl, chatcmpl, anthropicmsgs, moonshotchatcmpl, deepseekchatcmpl, ollamachat, giteeaichatcmpl, volcarkchatcmpl, xaichatcmpl, zhipuaichatcmpl, lmstudiochatcmpl, siliconflowchatcmpl, volcarkchatcmpl

FETCH_MODEL_LIST_URL = "https://api.qchatgpt.rockchin.top/api/v2/fetch/model_list"


class RuntimeLLMModel:
    """运行时模型"""

    model_entity: model.LLMModel
    """模型数据"""

    token_mgr: token.TokenManager
    """api key管理器"""

    requester: requester.LLMAPIRequester
    """请求器实例"""
    
    def __init__(self, model_entity: model.LLMModel, token_mgr: token.TokenManager, requester: requester.LLMAPIRequester):
        self.model_entity = model_entity
        self.token_mgr = token_mgr
        self.requester = requester


class ModelManager:
    """模型管理器"""

    model_list: list[entities.LLMModelInfo]  # deprecated

    requesters: dict[str, requester.LLMAPIRequester]  # deprecated

    token_mgrs: dict[str, token.TokenManager]  # deprecated

    # ====== 4.0 ======

    ap: app.Application

    llm_models: list[RuntimeLLMModel]

    requester_components: list[engine.Component]
    
    def __init__(self, ap: app.Application):
        self.ap = ap
        self.requester_components = []
        self.model_list = []
        self.requesters = {}
        self.token_mgrs = {}
        self.llm_models = []

    async def get_model_by_name(self, name: str) -> entities.LLMModelInfo:
        """通过名称获取模型
        """
        for model in self.model_list:
            if model.name == name:
                return model
        raise ValueError(f"无法确定模型 {name} 的信息，请在元数据中配置")
    
    async def initialize(self):

        self.requester_components = self.ap.discover.get_components_by_kind('LLMAPIRequester')

        # 初始化token_mgr, requester
        for k, v in self.ap.provider_cfg.data['keys'].items():
            self.token_mgrs[k] = token.TokenManager(k, v)

        for component in self.requester_components:
            api_cls = component.get_python_component_class()
            api_inst = api_cls(self.ap)
            await api_inst.initialize()
            self.requesters[component.metadata.name] = api_inst

        # 尝试从api获取最新的模型信息
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method="GET",
                    url=FETCH_MODEL_LIST_URL,
                    # 参数
                    params={
                        "version": self.ap.ver_mgr.get_current_version()
                    },
                ) as resp:
                    model_list = (await resp.json())['data']['list']

                    for model in model_list:

                        for index, local_model in enumerate(self.ap.llm_models_meta.data['list']):
                            if model['name'] == local_model['name']:
                                self.ap.llm_models_meta.data['list'][index] = model
                                break
                        else:
                            self.ap.llm_models_meta.data['list'].append(model)

                    await self.ap.llm_models_meta.dump_config()

        except Exception as e:
            self.ap.logger.debug(f'获取最新模型列表失败: {e}')

        default_model_info: entities.LLMModelInfo = None

        for model in self.ap.llm_models_meta.data['list']:
            if model['name'] == 'default':
                default_model_info = entities.LLMModelInfo(
                    name=model['name'],
                    model_name=None,
                    token_mgr=self.token_mgrs[model['token_mgr']],
                    requester=self.requesters[model['requester']],
                    tool_call_supported=model['tool_call_supported'],
                    vision_supported=model['vision_supported']
                )
                break

        for model in self.ap.llm_models_meta.data['list']:

            try:

                model_name = model.get('model_name', default_model_info.model_name)
                token_mgr = self.token_mgrs[model['token_mgr']] if 'token_mgr' in model else default_model_info.token_mgr
                req = self.requesters[model['requester']] if 'requester' in model else default_model_info.requester
                tool_call_supported = model.get('tool_call_supported', default_model_info.tool_call_supported)
                vision_supported = model.get('vision_supported', default_model_info.vision_supported)

                model_info = entities.LLMModelInfo(
                    name=model['name'],
                    model_name=model_name,
                    token_mgr=token_mgr,
                    requester=req,
                    tool_call_supported=tool_call_supported,
                    vision_supported=vision_supported
                )
                self.model_list.append(model_info)
            
            except Exception as e:
                self.ap.logger.error(f"初始化模型 {model['name']} 失败: {type(e)} {e} ,请检查配置文件")

    def get_available_requesters_info(self) -> list[dict]:
        """获取所有可用的请求器"""
        return [
            component.to_plain_dict()
            for component in self.requester_components
        ]

    def get_available_requester_info_by_name(self, name: str) -> dict | None:
        """通过名称获取请求器信息"""
        for component in self.requester_components:
            if component.metadata.name == name:
                return component.to_plain_dict()
        return None
