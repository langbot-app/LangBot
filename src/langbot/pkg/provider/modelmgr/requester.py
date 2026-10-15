from __future__ import annotations

from contextlib import aclosing

import abc
import asyncio
import typing
import time

from ...core import app
from ...api.http.context import ExecutionContext
from ...entity.persistence import model as persistence_model
from ...workspace.errors import WorkspaceInvariantError
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from . import token
from . import reasoning
from . import request_policy
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


LLM_USAGE_QUERY_VARIABLE = '_llm_usage'
STREAM_USAGE_QUERY_VARIABLE = '_stream_usage'


def _ensure_same_execution_scope(
    expected: ExecutionContext,
    actual: ExecutionContext,
    *,
    resource: str,
) -> None:
    if (
        actual.instance_uuid != expected.instance_uuid
        or actual.workspace_uuid != expected.workspace_uuid
        or actual.placement_generation != expected.placement_generation
    ):
        raise WorkspaceInvariantError(f'{resource} belongs to another Workspace execution scope')


def _store_llm_usage(query: pipeline_query.Query | None, usage_info: dict | None) -> None:
    """Store the latest provider usage on the query for upstream action handlers."""
    if query is None or not usage_info:
        return
    if query.variables is None:
        query.variables = {}
    query.variables[LLM_USAGE_QUERY_VARIABLE] = dict(usage_info)


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
        execution_context: ExecutionContext,
        provider_entity: persistence_model.ModelProvider,
        token_mgr: token.TokenManager,
        requester: ProviderAPIRequester,
    ):
        if provider_entity.workspace_uuid != execution_context.workspace_uuid:
            raise WorkspaceInvariantError('Provider belongs to another Workspace')
        self.execution_context = execution_context
        self.provider_entity = provider_entity
        self.token_mgr = token_mgr
        self.requester = requester

    def _validate_invocation(
        self,
        model: RuntimeLLMModel | RuntimeEmbeddingModel | RuntimeRerankModel,
        execution_context: ExecutionContext,
    ) -> None:
        _ensure_same_execution_scope(self.execution_context, execution_context, resource='Provider invocation')
        _ensure_same_execution_scope(self.execution_context, model.execution_context, resource='Runtime model')
        if model.provider is not self:
            raise WorkspaceInvariantError('Runtime model is attached to another provider')

    def _resolve_llm_execution_context(
        self,
        query: pipeline_query.Query | None,
        execution_context: ExecutionContext | None,
    ) -> ExecutionContext:
        if query is not None:
            from ...pipeline.pool import get_query_execution_context

            query_context = get_query_execution_context(query)
            if execution_context is not None:
                _ensure_same_execution_scope(
                    query_context,
                    execution_context,
                    resource='Explicit LLM invocation context',
                )
            return query_context
        if execution_context is None:
            raise WorkspaceInvariantError('LLM invocation requires an ExecutionContext when query is absent')
        return execution_context

    def _call_state(self, query, model, extra_args, context):
        config = getattr(self.requester, 'requester_cfg', {})
        policy = request_policy.RequestPolicy.resolve(config, model.model_entity.extra_args, extra_args)
        if query is not None:
            if query.variables is None:
                query.variables = {}
            query.variables.pop(LLM_USAGE_QUERY_VARIABLE, None)
            query.variables.pop(STREAM_USAGE_QUERY_VARIABLE, None)
        return request_policy.CallState(policy, request_policy.opaque_conversation_id(query, context))

    async def _record_call(self, query, model, state, status, error):
        state.mark('total_ms')
        if query is None:
            return
        stream_usage = query.variables.pop(STREAM_USAGE_QUERY_VARIABLE, None)
        usage = state.usage if state.usage is not None else stream_usage
        if usage is not None:
            _store_llm_usage(query, usage)
        details = {'timing': dict(state.metrics), 'usage': usage, 'error': error}
        query.variables['_llm_diagnostics'] = details
        try:
            from ...pipeline import monitoring_helper

            await monitoring_helper.MonitoringHelper.record_llm_call(
                ap=self.requester.ap,
                query=query,
                bot_id=query.bot_uuid or 'unknown',
                bot_name=query.variables.get('_monitoring_bot_name', 'Unknown'),
                pipeline_id=query.pipeline_uuid or 'unknown',
                pipeline_name=query.variables.get('_monitoring_pipeline_name', 'Unknown'),
                model_name=model.model_entity.name,
                input_tokens=(usage or {}).get('prompt_tokens', 0) or 0,
                output_tokens=(usage or {}).get('completion_tokens', 0) or 0,
                duration_ms=int(state.metrics['total_ms']),
                status=status,
                error_message=error.get('message') if error else None,
                message_id=query.variables.get('_monitoring_message_id'),
                details=details,
            )
        except Exception as exc:
            self.requester.ap.logger.error(f'[Monitoring] Failed to record LLM call: {exc}')

    async def invoke_llm(
        self,
        query: pipeline_query.Query | None,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
        execution_context: ExecutionContext | None = None,
    ) -> provider_message.Message:
        """Preserve the legacy Message return while owning retries and deadlines."""
        context = self._resolve_llm_execution_context(query, execution_context)
        self._validate_invocation(model, context)
        state = self._call_state(query, model, extra_args, context)
        status, error = 'success', None
        try:
            while True:
                state.metrics['attempts'] += 1
                state.attempt_start = time.perf_counter()
                try:
                    result = await state.wait(
                        lambda: self.requester.invoke_llm(
                            query=query,
                            model=model,
                            messages=messages,
                            funcs=funcs,
                            extra_args=extra_args,
                            remove_think=remove_think,
                        ),
                        'response',
                        state.policy.total_timeout,
                    )
                    state.mark('response_completed_ms')
                    if isinstance(result, tuple):
                        message, state.usage = result
                        return message
                    return result
                except Exception as exc:
                    if not await state.retry(exc):
                        raise
        except (asyncio.CancelledError, GeneratorExit):
            status, error = 'error', {'code': 'cancelled', 'message': 'LLM invocation cancelled'}
            raise
        except Exception as exc:
            status = 'error'
            error = exc.as_dict() if isinstance(exc, request_policy.STRUCTURED_ERRORS) else {'code': 'provider_error'}
            error['message'] = str(exc)
            raise
        finally:
            await self._record_call(query, model, state, status, error)

    async def invoke_llm_stream(
        self,
        query: pipeline_query.Query | None,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
        execution_context: ExecutionContext | None = None,
    ) -> typing.AsyncIterator[provider_message.MessageChunk]:
        """Never retry after a raw upstream event or a legacy adapter chunk."""
        context = self._resolve_llm_execution_context(query, execution_context)
        self._validate_invocation(model, context)
        state = self._call_state(query, model, extra_args, context)
        status, error = 'success', None
        try:
            while True:
                state.metrics['attempts'] += 1
                state.attempt_start = time.perf_counter()
                try:
                    async with aclosing(
                        self.requester.invoke_llm_stream(
                            query=query,
                            model=model,
                            messages=messages,
                            funcs=funcs,
                            extra_args=extra_args,
                            remove_think=remove_think,
                        )
                    ) as stream:
                        while True:
                            try:
                                chunk = await state.wait(
                                    lambda: anext(stream),
                                    'total'
                                    if getattr(self.requester, 'reports_raw_timing', False) is True
                                    else ('stream_idle' if state.raw_started else 'first_event'),
                                    state.policy.total_timeout
                                    if getattr(self.requester, 'reports_raw_timing', False) is True
                                    else (
                                        state.policy.stream_idle_timeout
                                        if state.raw_started
                                        else state.policy.first_event_timeout
                                    ),
                                )
                            except StopAsyncIteration:
                                break
                            if chunk is None:
                                continue
                            state.raw_started = True
                            state.mark('first_event_ms')
                            if chunk.content:
                                state.mark('first_visible_chunk_ms')
                            yield chunk
                    state.mark('response_completed_ms')
                    return
                except Exception as exc:
                    if not await state.retry(exc):
                        raise
        except (asyncio.CancelledError, GeneratorExit):
            status, error = 'error', {'code': 'cancelled', 'message': 'LLM stream cancelled'}
            raise
        except Exception as exc:
            status = 'error'
            error = exc.as_dict() if isinstance(exc, request_policy.STRUCTURED_ERRORS) else {'code': 'provider_error'}
            error['message'] = str(exc)
            raise
        finally:
            await self._record_call(query, model, state, status, error)

    async def invoke_embedding(
        self,
        model: RuntimeEmbeddingModel,
        input_text: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
        *,
        execution_context: ExecutionContext,
        knowledge_base_id: str | None = None,
        query_text: str | None = None,
        session_id: str | None = None,
        message_id: str | None = None,
        call_type: str | None = None,
    ) -> typing.List[typing.List[float]]:
        """Bridge method for invoking embedding with monitoring"""
        self._validate_invocation(model, execution_context)
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
                    execution_context,
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

    async def invoke_rerank(
        self,
        model: RuntimeRerankModel,
        query: str,
        documents: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
        *,
        execution_context: ExecutionContext,
    ) -> typing.List[dict]:
        """Bridge method for invoking rerank with monitoring"""
        self._validate_invocation(model, execution_context)
        start_time = time.time()
        status = 'success'

        try:
            result = await self.requester.invoke_rerank(
                model=model,
                query=query,
                documents=documents,
                extra_args=extra_args,
            )
            return result

        except Exception:
            status = 'error'
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)

            try:
                self.requester.ap.logger.debug(
                    f'[Rerank] model={model.model_entity.name} docs={len(documents)} '
                    f'duration={duration_ms}ms status={status}'
                )
            except Exception as monitor_err:
                self.requester.ap.logger.error(f'[Monitoring] Failed to record rerank call: {monitor_err}')


class RuntimeLLMModel:
    """运行时模型"""

    model_entity: persistence_model.LLMModel
    """模型数据"""

    provider: RuntimeProvider
    """提供商实例"""

    reasoning_config_override: dict[str, typing.Any] | None
    """Request-scoped reasoning policy supplied by the active pipeline."""

    def __init__(
        self,
        execution_context: ExecutionContext,
        model_entity: persistence_model.LLMModel,
        provider: RuntimeProvider,
        reasoning_config_override: dict[str, typing.Any] | None = None,
    ):
        _ensure_same_execution_scope(provider.execution_context, execution_context, resource='LLM model')
        if model_entity.workspace_uuid != execution_context.workspace_uuid:
            raise WorkspaceInvariantError('LLM model belongs to another Workspace')
        if model_entity.provider_uuid != provider.provider_entity.uuid:
            raise WorkspaceInvariantError('LLM model references another provider')
        self.execution_context = execution_context
        self.model_entity = model_entity
        self.provider = provider
        self.reasoning_config_override = reasoning_config_override


class RuntimeEmbeddingModel:
    """运行时 Embedding 模型"""

    model_entity: persistence_model.EmbeddingModel
    """模型数据"""

    provider: RuntimeProvider
    """提供商实例"""

    def __init__(
        self,
        execution_context: ExecutionContext,
        model_entity: persistence_model.EmbeddingModel,
        provider: RuntimeProvider,
    ):
        _ensure_same_execution_scope(provider.execution_context, execution_context, resource='Embedding model')
        if model_entity.workspace_uuid != execution_context.workspace_uuid:
            raise WorkspaceInvariantError('Embedding model belongs to another Workspace')
        if model_entity.provider_uuid != provider.provider_entity.uuid:
            raise WorkspaceInvariantError('Embedding model references another provider')
        self.execution_context = execution_context
        self.model_entity = model_entity
        self.provider = provider


class RuntimeRerankModel:
    """运行时 Rerank 模型"""

    model_entity: persistence_model.RerankModel
    """模型数据"""

    provider: RuntimeProvider
    """提供商实例"""

    def __init__(
        self,
        execution_context: ExecutionContext,
        model_entity: persistence_model.RerankModel,
        provider: RuntimeProvider,
    ):
        _ensure_same_execution_scope(provider.execution_context, execution_context, resource='Rerank model')
        if model_entity.workspace_uuid != execution_context.workspace_uuid:
            raise WorkspaceInvariantError('Rerank model belongs to another Workspace')
        if model_entity.provider_uuid != provider.provider_entity.uuid:
            raise WorkspaceInvariantError('Rerank model references another provider')
        self.execution_context = execution_context
        self.model_entity = model_entity
        self.provider = provider


class ProviderAPIRequester(metaclass=abc.ABCMeta):
    """Provider API请求器"""

    name: str = None
    init_api_key: str = 'langbot-init-placeholder'

    ap: app.Application

    default_config: dict[str, typing.Any] = {}

    requester_cfg: dict[str, typing.Any] = {}

    def __init__(self, ap: app.Application, config: dict[str, typing.Any]):
        self.ap = ap
        self.requester_cfg = {**self.default_config}
        self.requester_cfg.update(config)

    async def initialize(self):
        pass

    async def aclose(self) -> None:
        """Release requester-owned clients when its runtime provider retires.

        Most built-in requesters are currently stateless, but provider
        extensions may own connection pools or background resources. Keeping
        the lifecycle hook on the base class lets Workspace generation changes
        and application shutdown retire them deterministically.
        """

        return None

    async def scan_models(self, api_key: str | None = None) -> dict[str, typing.Any] | list[dict[str, typing.Any]]:
        """Scan models supported by the provider.

        The default implementation does not support scanning. Requesters that
        can enumerate remote models should override this method.
        """
        raise NotImplementedError('This provider does not support model scanning')

    def get_reasoning_capabilities(self, model: RuntimeLLMModel) -> dict[str, typing.Any]:
        """Return normalized reasoning controls supported by a model."""
        return reasoning.default_reasoning_capabilities(
            supported='reasoning' in (model.model_entity.abilities or []),
            source='manual' if 'reasoning' in (model.model_entity.abilities or []) else 'unknown',
        )

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

    async def count_tokens(
        self,
        model: RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> int:
        """Count model input tokens before invoking the model.

        Requesters should use the same provider/model conversion path as
        ``invoke_llm`` so the preflight count matches the actual request shape.
        """
        raise NotImplementedError('This requester does not support token counting')

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

    async def invoke_rerank(
        self,
        model: RuntimeRerankModel,
        query: str,
        documents: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> typing.List[dict]:
        """调用 Rerank API

        Args:
            model (RuntimeRerankModel): 使用的模型信息
            query (str): 查询文本
            documents (typing.List[str]): 待重排序的文档列表
            extra_args (dict[str, typing.Any], optional): 额外的参数. Defaults to {}.

        Returns:
            typing.List[dict]: [{"index": int, "relevance_score": float}, ...]
        """
        raise NotImplementedError('This requester does not support rerank')
