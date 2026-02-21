from __future__ import annotations

import abc
import typing
import time

from ...core import app
from ...entity.persistence import model as persistence_model
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from . import token
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class RuntimeProvider:
    """运行时模型提供商"""

    provider_entity: persistence_model.ModelProvider
    """提供商数据"""

    token_mgr: token.TokenManager
    """api key管理器"""

    requester: ProviderAPIRequester
    """请求器实例"""

    def __init__(
        self,
        provider_entity: persistence_model.ModelProvider,
        token_mgr: token.TokenManager,
        requester: ProviderAPIRequester,
    ):
        self.provider_entity = provider_entity
        self.token_mgr = token_mgr
        self.requester = requester

    async def invoke_llm(
        self,
        query: pipeline_query.Query,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
        """Bridge method for invoking LLM with monitoring"""
        # Start timing for monitoring
        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        status = 'success'
        error_message = None

        try:
            # Call the underlying requester
            result = await self.requester.invoke_llm(
                query=query,
                model=model,
                messages=messages,
                funcs=funcs,
                extra_args=extra_args,
                remove_think=remove_think,
            )

            # Try to extract token usage if the requester returns it
            # For requesters that return tuple (message, usage_info)
            if isinstance(result, tuple):
                msg, usage_info = result
                if usage_info:
                    input_tokens = usage_info.get('input_tokens', 0)
                    output_tokens = usage_info.get('output_tokens', 0)
                return msg
            else:
                return result

        except Exception as e:
            status = 'error'
            error_message = str(e)
            raise
        finally:
            # Record LLM call monitoring data (only if query is provided)
            if query is not None:
                duration_ms = int((time.time() - start_time) * 1000)

                # Import monitoring helper
                try:
                    from ...pipeline import monitoring_helper

                    # Get monitoring metadata from query variables
                    if query.variables:
                        bot_name = query.variables.get('_monitoring_bot_name', 'Unknown')
                        pipeline_name = query.variables.get('_monitoring_pipeline_name', 'Unknown')
                        message_id = query.variables.get('_monitoring_message_id')
                    else:
                        bot_name = 'Unknown'
                        pipeline_name = 'Unknown'
                        message_id = None

                    await monitoring_helper.MonitoringHelper.record_llm_call(
                        ap=self.requester.ap,
                        query=query,
                        bot_id=query.bot_uuid or 'unknown',
                        bot_name=bot_name,
                        pipeline_id=query.pipeline_uuid or 'unknown',
                        pipeline_name=pipeline_name,
                        model_name=model.model_entity.name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        duration_ms=duration_ms,
                        status=status,
                        error_message=error_message,
                        message_id=message_id,
                    )
                except Exception as monitor_err:
                    self.requester.ap.logger.error(f'[Monitoring] Failed to record LLM call: {monitor_err}')

    async def invoke_llm_stream(
        self,
        query: pipeline_query.Query,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.MessageChunk:
        """Bridge method for invoking LLM stream with monitoring"""
        # Start timing for monitoring
        start_time = time.time()
        status = 'success'
        error_message = None
        # Note: Stream doesn't easily provide token counts, set to 0
        input_tokens = 0
        output_tokens = 0

        try:
            # Stream the response
            async for chunk in self.requester.invoke_llm_stream(
                query=query,
                model=model,
                messages=messages,
                funcs=funcs,
                extra_args=extra_args,
                remove_think=remove_think,
            ):
                yield chunk
        except Exception as e:
            status = 'error'
            error_message = str(e)
            raise
        finally:
            # Record LLM call monitoring data (only if query is provided)
            if query is not None:
                duration_ms = int((time.time() - start_time) * 1000)

                # Import monitoring helper
                try:
                    from ...pipeline import monitoring_helper

                    # Get monitoring metadata from query variables
                    if query.variables:
                        bot_name = query.variables.get('_monitoring_bot_name', 'Unknown')
                        pipeline_name = query.variables.get('_monitoring_pipeline_name', 'Unknown')
                        message_id = query.variables.get('_monitoring_message_id')
                    else:
                        bot_name = 'Unknown'
                        pipeline_name = 'Unknown'
                        message_id = None

                    await monitoring_helper.MonitoringHelper.record_llm_call(
                        ap=self.requester.ap,
                        query=query,
                        bot_id=query.bot_uuid or 'unknown',
                        bot_name=bot_name,
                        pipeline_id=query.pipeline_uuid or 'unknown',
                        pipeline_name=pipeline_name,
                        model_name=model.model_entity.name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        duration_ms=duration_ms,
                        status=status,
                        error_message=error_message,
                        message_id=message_id,
                    )
                except Exception as monitor_err:
                    self.requester.ap.logger.error(f'[Monitoring] Failed to record LLM stream call: {monitor_err}')

    async def invoke_embedding(
        self,
        model: RuntimeEmbeddingModel,
        input_text: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
        knowledge_base_id: str | None = None,
        query_text: str | None = None,
        session_id: str | None = None,
        message_id: str | None = None,
        call_type: str | None = None,
    ) -> typing.List[typing.List[float]]:
        """Bridge method for invoking embedding with monitoring"""
        # Start timing for monitoring
        start_time = time.time()
        prompt_tokens = 0
        total_tokens = 0
        status = 'success'
        error_message = None

        try:
            # Call the underlying requester
            result = await self.requester.invoke_embedding(
                model=model,
                input_text=input_text,
                extra_args=extra_args,
            )

            # Handle both old format (list only) and new format (tuple with usage)
            if isinstance(result, tuple):
                embeddings, usage_info = result
                if usage_info:
                    prompt_tokens = usage_info.get('prompt_tokens', 0)
                    total_tokens = usage_info.get('total_tokens', 0)
                return embeddings
            else:
                return result

        except Exception as e:
            status = 'error'
            error_message = str(e)
            raise
        finally:
            # Record embedding call monitoring data
            duration_ms = int((time.time() - start_time) * 1000)

            try:
                await self.requester.ap.monitoring_service.record_embedding_call(
                    model_name=model.model_entity.name,
                    prompt_tokens=prompt_tokens,
                    total_tokens=total_tokens,
                    duration=duration_ms,
                    input_count=len(input_text),
                    status=status,
                    error_message=error_message,
                    knowledge_base_id=knowledge_base_id,
                    query_text=query_text,
                    session_id=session_id,
                    message_id=message_id,
                    call_type=call_type,
                )
            except Exception as monitor_err:
                self.requester.ap.logger.error(f'[Monitoring] Failed to record embedding call: {monitor_err}')


class RuntimeLLMModel:
    """运行时模型"""

    model_entity: persistence_model.LLMModel
    """模型数据"""

    provider: RuntimeProvider
    """提供商实例"""

    def __init__(
        self,
        model_entity: persistence_model.LLMModel,
        provider: RuntimeProvider,
    ):
        self.model_entity = model_entity
        self.provider = provider


class RuntimeEmbeddingModel:
    """运行时 Embedding 模型"""

    model_entity: persistence_model.EmbeddingModel
    """模型数据"""

    provider: RuntimeProvider
    """提供商实例"""

    def __init__(
        self,
        model_entity: persistence_model.EmbeddingModel,
        provider: RuntimeProvider,
    ):
        self.model_entity = model_entity
        self.provider = provider


class ProviderAPIRequester(metaclass=abc.ABCMeta):
    """Provider API请求器"""

    name: str = None

    ap: app.Application

    default_config: dict[str, typing.Any] = {}

    requester_cfg: dict[str, typing.Any] = {}

    def __init__(self, ap: app.Application, config: dict[str, typing.Any]):
        self.ap = ap
        self.requester_cfg = {**self.default_config}
        self.requester_cfg.update(config)

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def invoke_llm(
        self,
        query: pipeline_query.Query,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
        """调用API

        Args:
            model (RuntimeLLMModel): 使用的模型信息
            messages (typing.List[llm_entities.Message]): 消息对象列表
            funcs (typing.List[tools_entities.LLMFunction], optional): 使用的工具函数列表. Defaults to None.
            extra_args (dict[str, typing.Any], optional): 额外的参数. Defaults to {}.
            remove_think (bool, optional): 是否移思考中的消息. Defaults to False.

        Returns:
            llm_entities.Message: 返回消息对象
        """
        pass

    async def invoke_llm_stream(
        self,
        query: pipeline_query.Query,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.MessageChunk:
        """调用API

        Args:
            model (RuntimeLLMModel): 使用的模型信息
            messages (typing.List[provider_message.Message]): 消息对象列表
            funcs (typing.List[resource_tool.LLMTool], optional): 使用的工具函数列表. Defaults to None.
            extra_args (dict[str, typing.Any], optional): 额外的参数. Defaults to {}.
            remove_think (bool, optional): 是否移除思考中的消息. Defaults to False.

        Returns:
            typing.AsyncGenerator[provider_message.MessageChunk]: 返回消息对象
        """
        pass

    async def invoke_embedding(
        self,
        model: RuntimeEmbeddingModel,
        input_text: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> typing.Union[typing.List[typing.List[float]], tuple[typing.List[typing.List[float]], dict]]:
        """调用 Embedding API

        Args:
            model (RuntimeEmbeddingModel): 使用的模型信息
            input_text (typing.List[str]): 输入文本
            extra_args (dict[str, typing.Any], optional): 额外的参数. Defaults to {}.

        Returns:
            typing.List[typing.List[float]]: 返回的 embedding 向量
            或者 tuple[typing.List[typing.List[float]], dict]: 返回 (embedding 向量, usage_info)
        """
        pass
