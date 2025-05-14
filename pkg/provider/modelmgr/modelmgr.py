from __future__ import annotations

import sqlalchemy

from . import entities, requester
from ...core import app
from ...core import entities as core_entities
from .. import entities as llm_entities
from ..tools import entities as tools_entities
from ...discover import engine
from . import token
from ...entity.persistence import model as persistence_model

FETCH_MODEL_LIST_URL = 'https://api.qchatgpt.rockchin.top/api/v2/fetch/model_list'


class ModelManager:
    """模型管理器"""

    model_list: list[entities.LLMModelInfo]  # deprecated

    requesters: dict[str, requester.LLMAPIRequester]  # deprecated

    token_mgrs: dict[str, token.TokenManager]  # deprecated

    # ====== 4.0 ======

    ap: app.Application

    llm_models: list[requester.RuntimeLLMModel]

    requester_components: list[engine.Component]

    requester_dict: dict[str, type[requester.LLMAPIRequester]]  # cache

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.model_list = []
        self.requesters = {}
        self.token_mgrs = {}
        self.llm_models = []
        self.requester_components = []
        self.requester_dict = {}

    async def initialize(self):
        self.requester_components = self.ap.discover.get_components_by_kind('LLMAPIRequester')

        # forge requester class dict
        requester_dict: dict[str, type[requester.LLMAPIRequester]] = {}
        for component in self.requester_components:
            requester_dict[component.metadata.name] = component.get_python_component_class()

        self.requester_dict = requester_dict

        await self.load_models_from_db()

    async def load_models_from_db(self):
        """从数据库加载模型"""
        self.ap.logger.info('Loading models from db...')

        self.llm_models = []

        # llm models
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.LLMModel))

        llm_models = result.all()

        # load models
        for llm_model in llm_models:
            await self.load_llm_model(llm_model)

    async def load_llm_model(
        self,
        model_info: persistence_model.LLMModel | sqlalchemy.Row[persistence_model.LLMModel] | dict,
    ):
        """加载模型"""

        if isinstance(model_info, sqlalchemy.Row):
            model_info = persistence_model.LLMModel(**model_info._mapping)
        elif isinstance(model_info, dict):
            model_info = persistence_model.LLMModel(**model_info)

        requester_inst = self.requester_dict[model_info.requester](ap=self.ap, config=model_info.requester_config)

        await requester_inst.initialize()

        runtime_llm_model = requester.RuntimeLLMModel(
            model_entity=model_info,
            token_mgr=token.TokenManager(
                name=model_info.uuid,
                tokens=model_info.api_keys,
            ),
            requester=requester_inst,
        )
        self.llm_models.append(runtime_llm_model)

    async def get_model_by_name(self, name: str) -> entities.LLMModelInfo:  # deprecated
        """通过名称获取模型"""
        for model in self.model_list:
            if model.name == name:
                return model
        raise ValueError(f'无法确定模型 {name} 的信息')

    async def get_model_by_uuid(self, uuid: str) -> entities.LLMModelInfo:
        """通过uuid获取模型"""
        for model in self.llm_models:
            if model.model_entity.uuid == uuid:
                return model
        raise ValueError(f'model {uuid} not found')

    async def remove_llm_model(self, model_uuid: str):
        """移除模型"""
        for model in self.llm_models:
            if model.model_entity.uuid == model_uuid:
                self.llm_models.remove(model)
                return

    def get_available_requesters_info(self) -> list[dict]:
        """获取所有可用的请求器"""
        return [component.to_plain_dict() for component in self.requester_components]

    def get_available_requester_info_by_name(self, name: str) -> dict | None:
        """通过名称获取请求器信息"""
        for component in self.requester_components:
            if component.metadata.name == name:
                return component.to_plain_dict()
        return None

    def get_available_requester_manifest_by_name(self, name: str) -> engine.Component | None:
        """通过名称获取请求器清单"""
        for component in self.requester_components:
            if component.metadata.name == name:
                return component
        return None

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model_uuid: str,
        messages: list[llm_entities.Message],
        funcs: list[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        pass
