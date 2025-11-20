from __future__ import annotations

import sqlalchemy
import traceback

from . import requester
from ...core import app
from ...discover import engine
from . import token
from ...entity.persistence import model as persistence_model
from ...entity.errors import provider as provider_errors

FETCH_MODEL_LIST_URL = 'https://api.qchatgpt.rockchin.top/api/v2/fetch/model_list'


class ModelManager:
    """模型管理器"""

    ap: app.Application

    llm_models: list[requester.RuntimeLLMModel]

    embedding_models: list[requester.RuntimeEmbeddingModel]

    requester_components: list[engine.Component]

    requester_dict: dict[str, type[requester.ProviderAPIRequester]]  # cache

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.llm_models = []
        self.embedding_models = []
        self.requester_components = []
        self.requester_dict = {}

    async def initialize(self):
        self.requester_components = self.ap.discover.get_components_by_kind('LLMAPIRequester')

        # forge requester class dict
        requester_dict: dict[str, type[requester.ProviderAPIRequester]] = {}
        for component in self.requester_components:
            requester_dict[component.metadata.name] = component.get_python_component_class()

        self.requester_dict = requester_dict

        await self.load_models_from_db()

    async def load_models_from_db(self):
        """从数据库加载模型"""
        self.ap.logger.info('Loading models from db...')

        self.llm_models = []
        self.embedding_models = []

        # llm models
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.LLMModel))
        llm_models = result.all()
        for llm_model in llm_models:
            try:
                await self.load_llm_model(llm_model)
            except provider_errors.RequesterNotFoundError as e:
                self.ap.logger.warning(f'Requester {e.requester_name} not found, skipping llm model {llm_model.uuid}')
            except Exception as e:
                self.ap.logger.error(f'Failed to load model {llm_model.uuid}: {e}\n{traceback.format_exc()}')

        # embedding models
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.EmbeddingModel))
        embedding_models = result.all()
        for embedding_model in embedding_models:
            try:
                await self.load_embedding_model(embedding_model)
            except provider_errors.RequesterNotFoundError as e:
                self.ap.logger.warning(
                    f'Requester {e.requester_name} not found, skipping embedding model {embedding_model.uuid}'
                )
            except Exception as e:
                self.ap.logger.error(f'Failed to load model {embedding_model.uuid}: {e}\n{traceback.format_exc()}')

    async def init_runtime_llm_model(
        self,
        model_info: persistence_model.LLMModel | sqlalchemy.Row[persistence_model.LLMModel] | dict,
    ):
        """初始化运行时 LLM 模型"""
        if isinstance(model_info, sqlalchemy.Row):
            model_info = persistence_model.LLMModel(**model_info._mapping)
        elif isinstance(model_info, dict):
            model_info = persistence_model.LLMModel(**model_info)

        if model_info.requester not in self.requester_dict:
            raise provider_errors.RequesterNotFoundError(model_info.requester)

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

        return runtime_llm_model

    async def init_runtime_embedding_model(
        self,
        model_info: persistence_model.EmbeddingModel | sqlalchemy.Row[persistence_model.EmbeddingModel] | dict,
    ):
        """初始化运行时 Embedding 模型"""
        if isinstance(model_info, sqlalchemy.Row):
            model_info = persistence_model.EmbeddingModel(**model_info._mapping)
        elif isinstance(model_info, dict):
            model_info = persistence_model.EmbeddingModel(**model_info)

        if model_info.requester not in self.requester_dict:
            raise provider_errors.RequesterNotFoundError(model_info.requester)

        requester_inst = self.requester_dict[model_info.requester](ap=self.ap, config=model_info.requester_config)

        await requester_inst.initialize()

        runtime_embedding_model = requester.RuntimeEmbeddingModel(
            model_entity=model_info,
            token_mgr=token.TokenManager(
                name=model_info.uuid,
                tokens=model_info.api_keys,
            ),
            requester=requester_inst,
        )

        return runtime_embedding_model

    async def load_llm_model(
        self,
        model_info: persistence_model.LLMModel | sqlalchemy.Row[persistence_model.LLMModel] | dict,
    ):
        """加载 LLM 模型"""
        runtime_llm_model = await self.init_runtime_llm_model(model_info)
        self.llm_models.append(runtime_llm_model)

    async def load_embedding_model(
        self,
        model_info: persistence_model.EmbeddingModel | sqlalchemy.Row[persistence_model.EmbeddingModel] | dict,
    ):
        """加载 Embedding 模型"""
        runtime_embedding_model = await self.init_runtime_embedding_model(model_info)
        self.embedding_models.append(runtime_embedding_model)

    async def get_model_by_uuid(self, uuid: str) -> requester.RuntimeLLMModel:
        """通过uuid获取 LLM 模型"""
        for model in self.llm_models:
            if model.model_entity.uuid == uuid:
                return model
        raise ValueError(f'LLM model {uuid} not found')

    async def get_embedding_model_by_uuid(self, uuid: str) -> requester.RuntimeEmbeddingModel:
        """通过uuid获取 Embedding 模型"""
        for model in self.embedding_models:
            if model.model_entity.uuid == uuid:
                return model
        raise ValueError(f'Embedding model {uuid} not found')

    async def remove_llm_model(self, model_uuid: str):
        """移除 LLM 模型"""
        for model in self.llm_models:
            if model.model_entity.uuid == model_uuid:
                self.llm_models.remove(model)
                return

    async def remove_embedding_model(self, model_uuid: str):
        """移除 Embedding 模型"""
        for model in self.embedding_models:
            if model.model_entity.uuid == model_uuid:
                self.embedding_models.remove(model)
                return

    def get_available_requesters_info(self, model_type: str) -> list[dict]:
        """获取所有可用的请求器"""
        if model_type != '':
            return [
                component.to_plain_dict()
                for component in self.requester_components
                if model_type in component.spec['support_type']
            ]
        else:
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
