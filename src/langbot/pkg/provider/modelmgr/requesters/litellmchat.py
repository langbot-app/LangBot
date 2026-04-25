"""LiteLLM unified requester for chat, embedding, and rerank."""

from __future__ import annotations

import typing

import litellm
from litellm import acompletion, aembedding, arerank

from .. import errors, requester
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class LiteLLMRequester(requester.ProviderAPIRequester):
    """LiteLLM unified API requester supporting chat, embedding, and rerank."""

    default_config: dict[str, typing.Any] = {
        'base_url': '',
        'timeout': 120,
        'custom_llm_provider': '',
        'drop_params': False,
        'num_retries': 0,
        'api_version': '',
    }

    async def initialize(self):
        """Initialize LiteLLM client settings."""
        # LiteLLM doesn't require explicit client initialization
        # Configuration is passed per-request via litellm params
        pass

    def _build_litellm_model_name(self, model_name: str, custom_llm_provider: str | None = None) -> str:
        """Build LiteLLM model name with provider prefix if needed."""
        provider = custom_llm_provider or self.requester_cfg.get('custom_llm_provider', '')
        if provider:
            # LiteLLM format: provider/model_name
            return f'{provider}/{model_name}'
        # If no custom provider, assume model_name already includes prefix or is OpenAI-compatible
        return model_name

    def _convert_messages(self, messages: typing.List[provider_message.Message]) -> list[dict]:
        """Convert LangBot messages to LiteLLM/OpenAI format."""
        req_messages = []
        for m in messages:
            msg_dict = m.dict(exclude_none=True)
            content = msg_dict.get('content')

            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get('type') == 'image_base64':
                        part['image_url'] = {'url': part['image_base64']}
                        part['type'] = 'image_url'
                        del part['image_base64']

            req_messages.append(msg_dict)

        return req_messages

    def _process_thinking_content(self, content: str, reasoning_content: str | None, remove_think: bool) -> str:
        """Process thinking/reasoning content.

        Args:
            content: The main content from response
            reasoning_content: Separate reasoning content from model
            remove_think: If True, remove thinking markers; if False, preserve them

        Returns:
            Processed content string
        """
        # Extract and handle thinking tags
        if content and 'CRETIRE_REASONING_BEGINk' in content and 'CRETIRE_REASONING_ENDk' in content:
            import re

            think_pattern = r'CRETIRE_REASONING_BEGINk(.*?)CRETIRE_REASONING_ENDk'

            if remove_think:
                # Remove thinking tags and their content from output
                content = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()
            # else: preserve thinking content as-is

        # Handle separate reasoning_content field
        # Currently we don't include reasoning_content in user-facing output regardless of remove_think
        # because it's typically internal model reasoning, not user-visible thinking
        return content or ''

    def _extract_usage(self, response) -> dict:
        """Extract usage info from LiteLLM response."""
        usage = response.usage
        return {
            'prompt_tokens': usage.prompt_tokens or 0,
            'completion_tokens': usage.completion_tokens or 0,
            'total_tokens': usage.total_tokens or 0,
        }

    def _build_common_args(self, args: dict, include_retry_params: bool = True) -> dict:
        """Apply common requester config to args dict."""
        if self.requester_cfg.get('base_url'):
            args['api_base'] = self.requester_cfg['base_url']
        if self.requester_cfg.get('timeout'):
            args['timeout'] = self.requester_cfg['timeout']
        if include_retry_params:
            if self.requester_cfg.get('drop_params'):
                args['drop_params'] = self.requester_cfg['drop_params']
            if self.requester_cfg.get('num_retries'):
                args['num_retries'] = self.requester_cfg['num_retries']
            if self.requester_cfg.get('api_version'):
                args['api_version'] = self.requester_cfg['api_version']
        return args

    def _handle_litellm_error(self, e: Exception) -> None:
        """Convert LiteLLM exceptions to RequesterError. Never returns, always raises."""
        # Check more specific exceptions first (they inherit from base exceptions)
        if isinstance(e, litellm.ContextWindowExceededError):
            raise errors.RequesterError(f'上下文长度超限: {str(e)}')
        if isinstance(e, litellm.BadRequestError):
            raise errors.RequesterError(f'请求参数错误: {str(e)}')
        if isinstance(e, litellm.AuthenticationError):
            raise errors.RequesterError(f'API key 无效: {str(e)}')
        if isinstance(e, litellm.NotFoundError):
            raise errors.RequesterError(f'模型或路径无效: {str(e)}')
        if isinstance(e, litellm.RateLimitError):
            raise errors.RequesterError(f'请求过于频繁或余额不足: {str(e)}')
        if isinstance(e, litellm.Timeout):
            raise errors.RequesterError(f'请求超时: {str(e)}')
        if isinstance(e, litellm.APIConnectionError):
            raise errors.RequesterError(f'连接错误: {str(e)}')
        if isinstance(e, litellm.APIError):
            raise errors.RequesterError(f'API 错误: {str(e)}')
        raise errors.RequesterError(f'未知错误: {str(e)}')

    async def _build_completion_args(
        self,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        stream: bool = False,
    ) -> dict:
        """Build common completion arguments for invoke_llm and invoke_llm_stream."""
        req_messages = self._convert_messages(messages)
        model_name = self._build_litellm_model_name(model.model_entity.name)
        api_key = model.provider.token_mgr.get_token()

        args = {
            'model': model_name,
            'messages': req_messages,
            'api_key': api_key,
        }
        if stream:
            args['stream'] = True
            args['stream_options'] = {'include_usage': True}
        self._build_common_args(args)
        args.update(extra_args)

        if funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(funcs)
            if tools:
                args['tools'] = tools

        return args

    async def invoke_llm(
        self,
        query: pipeline_query.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> tuple[provider_message.Message, dict]:
        """Invoke LLM and return message with usage info."""
        args = await self._build_completion_args(model, messages, funcs, extra_args, stream=False)

        try:
            response = await acompletion(**args)

            message_data = response.choices[0].message.model_dump()
            if 'role' not in message_data or message_data['role'] is None:
                message_data['role'] = 'assistant'

            content = message_data.get('content', '')
            reasoning_content = message_data.get('reasoning_content', None)
            message_data['content'] = self._process_thinking_content(content, reasoning_content, remove_think)

            if 'reasoning_content' in message_data:
                del message_data['reasoning_content']

            message = provider_message.Message(**message_data)
            usage_info = self._extract_usage(response)

            return message, usage_info

        except Exception as e:
            self._handle_litellm_error(e)

    async def invoke_llm_stream(
        self,
        query: pipeline_query.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.MessageChunk:
        """Invoke LLM streaming and yield chunks."""
        args = await self._build_completion_args(model, messages, funcs, extra_args, stream=True)

        chunk_idx = 0
        role = 'assistant'

        try:
            response = await acompletion(**args)
            async for chunk in response:
                # Check for usage chunk (final chunk with stream_options include_usage)
                if hasattr(chunk, 'usage') and chunk.usage and (not hasattr(chunk, 'choices') or not chunk.choices):
                    usage_info = {
                        'prompt_tokens': chunk.usage.prompt_tokens or 0,
                        'completion_tokens': chunk.usage.completion_tokens or 0,
                        'total_tokens': chunk.usage.total_tokens or 0,
                    }
                    if query:
                        if query.variables is None:
                            query.variables = {}
                        query.variables['_stream_usage'] = usage_info
                    continue

                if not hasattr(chunk, 'choices') or not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta.model_dump() if hasattr(choice, 'delta') else {}
                finish_reason = getattr(choice, 'finish_reason', None)

                if 'role' in delta and delta['role']:
                    role = delta['role']

                delta_content = delta.get('content', '')
                reasoning_content = delta.get('reasoning_content', '')

                if reasoning_content:
                    chunk_idx += 1
                    continue

                if chunk_idx == 0 and not delta_content and not delta.get('tool_calls'):
                    chunk_idx += 1
                    continue

                chunk_data = {
                    'role': role,
                    'content': delta_content if delta_content else None,
                    'tool_calls': delta.get('tool_calls'),
                    'is_final': bool(finish_reason),
                }

                chunk_data = {k: v for k, v in chunk_data.items() if v is not None}
                yield provider_message.MessageChunk(**chunk_data)
                chunk_idx += 1

        except Exception as e:
            self._handle_litellm_error(e)

    async def invoke_embedding(
        self,
        model: requester.RuntimeEmbeddingModel,
        input_text: list[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> tuple[list[list[float]], dict]:
        """Invoke embedding and return vectors with usage info."""
        model_name = self._build_litellm_model_name(model.model_entity.name)
        api_key = model.provider.token_mgr.get_token()

        args = {
            'model': model_name,
            'input': input_text,
            'api_key': api_key,
        }
        self._build_common_args(args, include_retry_params=False)

        if model.model_entity.extra_args:
            args.update(model.model_entity.extra_args)

        args.update(extra_args)

        try:
            response = await aembedding(**args)

            embeddings = [d.embedding for d in response.data]
            usage_info = self._extract_usage(response)

            return embeddings, usage_info

        except Exception as e:
            self._handle_litellm_error(e)

    async def invoke_rerank(
        self,
        model: requester.RuntimeRerankModel,
        query: str,
        documents: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> typing.List[dict]:
        """Invoke rerank and return relevance scores."""
        model_name = self._build_litellm_model_name(model.model_entity.name)
        api_key = model.provider.token_mgr.get_token()

        args = {
            'model': model_name,
            'query': query,
            'documents': documents,
            'api_key': api_key,
            'top_n': min(len(documents), 64),
        }
        self._build_common_args(args, include_retry_params=False)

        if model.model_entity.extra_args:
            args.update(model.model_entity.extra_args)

        args.update(extra_args)

        try:
            response = await arerank(**args)

            results = []
            for r in response.results:
                results.append(
                    {
                        'index': r.get('index', 0),
                        'relevance_score': r.get('relevance_score', 0.0),
                    }
                )

            if results:
                scores = [r['relevance_score'] for r in results]
                min_score = min(scores)
                max_score = max(scores)
                if max_score - min_score > 1e-6:
                    for r in results:
                        r['relevance_score'] = (r['relevance_score'] - min_score) / (max_score - min_score)

            return results

        except Exception as e:
            self._handle_litellm_error(e)

    async def scan_models(self, api_key: str | None = None) -> dict[str, typing.Any]:
        """Scan models supported by the provider."""
        import httpx

        base_url = self.requester_cfg.get('base_url', '').rstrip('/')
        timeout = self.requester_cfg.get('timeout', 120)

        if not base_url:
            raise errors.RequesterError('Base URL required for model scanning')

        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        models_url = f'{base_url}/models'

        try:
            async with httpx.AsyncClient(trust_env=True, timeout=timeout) as client:
                response = await client.get(models_url, headers=headers)
                response.raise_for_status()
                payload = response.json()

            models = []
            for item in payload.get('data', []):
                model_id = item.get('id')
                if not model_id:
                    continue

                # Infer model type
                normalized_id = (model_id or '').lower()
                embedding_keywords = ('embedding', 'embed', 'bge-', 'e5-', 'm3e', 'gte-', 'text-embedding')
                model_type = 'embedding' if any(kw in normalized_id for kw in embedding_keywords) else 'llm'

                models.append(
                    {
                        'id': model_id,
                        'name': model_id,
                        'type': model_type,
                    }
                )

            models.sort(key=lambda x: (x['type'] != 'llm', x['name'].lower()))

            return {'models': models}

        except httpx.HTTPStatusError as e:
            raise errors.RequesterError(f'Model scan failed: {e.response.status_code}')
        except httpx.TimeoutException:
            raise errors.RequesterError('Model scan timeout')
        except Exception as e:
            raise errors.RequesterError(f'Model scan error: {str(e)}')
