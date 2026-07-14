"""LiteLLM unified requester for chat, embedding, and rerank."""

from __future__ import annotations

import typing

import litellm
from litellm import acompletion, aembedding, arerank

from .. import errors, requester
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class _ThinkStripState:
    """Stateful filter that drops think blocks across chunks."""

    _THINK_OPEN = '<think>'
    _THINK_CLOSE = '</think>'
    _LEGACY_OPEN = 'CRETIRE_REASONING_BEGINk'
    _LEGACY_CLOSE = 'CRETIRE_REASONING_ENDk'

    def __init__(self) -> None:
        self._pairs: tuple[tuple[str, str], ...] = (
            (self._THINK_OPEN, self._THINK_CLOSE),
            (self._LEGACY_OPEN, self._LEGACY_CLOSE),
        )
        self._open_tags = tuple(open_tag for open_tag, _close_tag in self._pairs)
        self._buf = ''
        self._close_tag: str | None = None
        self._pending_initial = True

    def feed(self, chunk: str) -> str:
        """Feed a streaming delta and return user-visible content."""
        if not chunk:
            return chunk

        text = self._buf + chunk
        if self._close_tag is not None:
            return self._consume_think_body(text)

        return self._process_visible_text(text)

    def flush(self) -> str:
        """Release buffered visible content when the stream ends."""
        if self._close_tag is not None:
            self._buf = ''
            self._close_tag = None
            return ''

        pending, self._buf = self._buf, ''
        self._close_tag = None
        return pending

    def _consume_think_body(self, text: str) -> str:
        close_tag = self._close_tag
        if close_tag is None:
            return text

        close_idx = text.find(close_tag)
        if close_idx != -1:
            self._close_tag = None
            self._buf = ''
            self._pending_initial = False
            return self._process_visible_text(text[close_idx + len(close_tag) :])

        self._buf = self._close_prefix(text, close_tag)
        return ''

    def _process_visible_text(self, text: str) -> str:
        out: list[str] = []
        index = 0

        while index < len(text):
            if self._pending_initial:
                open_idx, open_tag, close_tag = self._find_next_open(text, index)
                orphan_close_idx, orphan_close_tag = self._find_next_close(text, index)

                if orphan_close_idx != -1 and (open_idx == -1 or orphan_close_idx < open_idx):
                    self._pending_initial = False
                    index = orphan_close_idx + len(orphan_close_tag)
                    continue

                if open_idx == -1:
                    self._buf = text[index:]
                    return ''.join(out)

                if open_idx > index:
                    self._pending_initial = False
                    out.append(text[index:open_idx])
                    index = open_idx
                    continue

            open_idx, open_tag, close_tag = self._find_next_open(text, index)
            if open_idx == -1:
                emit_end = self._visible_emit_end(text, index)
                out.append(text[index:emit_end])
                if emit_end > index:
                    self._pending_initial = False
                self._buf = text[emit_end:]
                return ''.join(out)

            out.append(text[index:open_idx])
            if open_idx > index:
                self._pending_initial = False
            body_start = open_idx + len(open_tag)
            close_idx = text.find(close_tag, body_start)
            if close_idx == -1:
                self._close_tag = close_tag
                self._buf = self._close_prefix(text[body_start:], close_tag)
                return ''.join(out)

            self._pending_initial = False
            index = close_idx + len(close_tag)

        self._buf = ''
        return ''.join(out)

    def _find_next_open(self, text: str, start: int) -> tuple[int, str, str]:
        best_idx = -1
        best_open = ''
        best_close = ''
        for open_tag, close_tag in self._pairs:
            idx = text.find(open_tag, start)
            if idx != -1 and (best_idx == -1 or idx < best_idx):
                best_idx = idx
                best_open = open_tag
                best_close = close_tag
        return best_idx, best_open, best_close

    def _find_next_close(self, text: str, start: int) -> tuple[int, str]:
        best_idx = -1
        best_close = ''
        for _open_tag, close_tag in self._pairs:
            idx = text.find(close_tag, start)
            if idx != -1 and (best_idx == -1 or idx < best_idx):
                best_idx = idx
                best_close = close_tag
        return best_idx, best_close

    def _visible_emit_end(self, text: str, start: int) -> int:
        visible = text[start:]
        limit = min(len(visible), max(len(open_tag) for open_tag in self._open_tags) - 1)
        for keep in range(limit, 0, -1):
            suffix = visible[-keep:]
            if any(open_tag.startswith(suffix) for open_tag in self._open_tags):
                return len(text) - keep
        return len(text)

    @staticmethod
    def _close_prefix(text: str, close_tag: str) -> str:
        limit = min(len(text), len(close_tag) - 1)
        for keep in range(limit, 0, -1):
            suffix = text[-keep:]
            if close_tag.startswith(suffix):
                return suffix
        return ''


class LiteLLMRequester(requester.ProviderAPIRequester):
    """LiteLLM unified API requester supporting chat, embedding, and rerank."""

    _EMBEDDING_MODEL_HINTS = ('embedding', 'embed', 'bge-', 'e5-', 'm3e', 'gte-', 'text-embedding')
    _RERANK_MODEL_HINTS = ('rerank', 're-rank', 're_rank')

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
            if model_name.startswith(f'{provider}/'):
                return model_name
            return f'{provider}/{model_name}'
        # If no custom provider, assume model_name already includes prefix or is OpenAI-compatible
        return model_name

    def _get_custom_llm_provider(self) -> str | None:
        return self.requester_cfg.get('custom_llm_provider') or None

    def _safe_litellm_bool_helper(self, helper_name: str, model_name: str) -> bool:
        """Call a LiteLLM boolean capability helper without letting metadata gaps fail requests."""
        helper = getattr(litellm, helper_name, None)
        if not callable(helper):
            return False

        provider = self._get_custom_llm_provider()
        candidates: list[tuple[str, str | None]] = [(model_name, provider)]
        litellm_model_name = self._build_litellm_model_name(model_name)
        if litellm_model_name != model_name:
            candidates.append((litellm_model_name, None))
        for metadata_provider in self._metadata_provider_candidates(model_name):
            candidates.append((f'{metadata_provider}/{model_name}', None))

        tried_candidates: set[tuple[str, str | None]] = set()
        for candidate_model, candidate_provider in candidates:
            candidate_key = (candidate_model, candidate_provider)
            if candidate_key in tried_candidates:
                continue
            tried_candidates.add(candidate_key)
            try:
                if bool(helper(model=candidate_model, custom_llm_provider=candidate_provider)):
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _positive_int(value: typing.Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            parsed_value = int(value)
            if parsed_value > 0:
                return parsed_value
        return None

    def _context_length_from_scan_payload(self, model_payload: dict[str, typing.Any] | None) -> int | None:
        if not model_payload:
            return None

        for field_name in ('context_length', 'context_window', 'max_context_length'):
            context_length = self._positive_int(model_payload.get(field_name))
            if context_length is not None:
                return context_length
        return None

    def _context_length_from_litellm_model_info(self, model_info: typing.Any) -> int | None:
        if isinstance(model_info, dict):
            return self._positive_int(model_info.get('max_input_tokens'))
        return self._positive_int(getattr(model_info, 'max_input_tokens', None))

    def _metadata_provider_candidates(self, model_name: str) -> list[str]:
        normalized_model_name = (model_name or '').lower()
        candidates = []
        if normalized_model_name.startswith(('moonshot-', 'kimi-')):
            candidates.append('moonshot')
        if normalized_model_name.startswith('deepseek-'):
            candidates.append('deepseek')

        base_url = self.requester_cfg.get('base_url', '').lower()
        if 'moonshot' in base_url:
            candidates.append('moonshot')
        if 'deepseek' in base_url:
            candidates.append('deepseek')

        deduped_candidates = []
        for candidate in candidates:
            if candidate not in deduped_candidates:
                deduped_candidates.append(candidate)
        return deduped_candidates

    def _known_context_length_fallback(self, model_name: str) -> int | None:
        normalized_model_name = (model_name or '').lower()
        if normalized_model_name.startswith('deepseek-v4-'):
            return 1_000_000
        if normalized_model_name.startswith(('kimi-k2.5', 'kimi-k2.6')):
            return 256 * 1024
        if normalized_model_name.startswith('moonshot-v1-8k'):
            return 8 * 1024
        if normalized_model_name.startswith('moonshot-v1-32k'):
            return 32 * 1024
        if normalized_model_name.startswith('moonshot-v1-128k') or normalized_model_name == 'moonshot-v1-auto':
            return 128 * 1024
        return None

    def _safe_context_length(self, model_name: str) -> int | None:
        helper = getattr(litellm, 'get_model_info', None)
        if not callable(helper):
            return self._known_context_length_fallback(model_name)

        candidates = [model_name]
        litellm_model_name = self._build_litellm_model_name(model_name)
        if litellm_model_name != model_name:
            candidates.append(litellm_model_name)
        for provider in self._metadata_provider_candidates(model_name):
            candidates.append(f'{provider}/{model_name}')

        tried_candidates = []
        for candidate in candidates:
            if candidate in tried_candidates:
                continue
            tried_candidates.append(candidate)
            try:
                model_info = helper(candidate)
            except Exception:
                continue
            context_length = self._context_length_from_litellm_model_info(model_info)
            if context_length is not None:
                return context_length
        return self._known_context_length_fallback(model_name)

    def _supports_function_calling(self, model_name: str) -> bool:
        return self._safe_litellm_bool_helper('supports_function_calling', model_name)

    def _supports_vision(self, model_name: str) -> bool:
        return self._safe_litellm_bool_helper('supports_vision', model_name)

    def _infer_model_type(self, model_id: str) -> str:
        normalized_id = (model_id or '').lower()
        if any(kw in normalized_id for kw in self._RERANK_MODEL_HINTS):
            return 'rerank'
        if any(kw in normalized_id for kw in self._EMBEDDING_MODEL_HINTS):
            return 'embedding'
        return 'llm'

    def _enrich_scanned_model(
        self,
        model_id: str,
        model_payload: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any]:
        model_type = self._infer_model_type(model_id)
        scanned_model: dict[str, typing.Any] = {
            'id': model_id,
            'name': model_id,
            'type': model_type,
        }

        if model_type == 'llm':
            abilities = []
            if self._supports_function_calling(model_id):
                abilities.append('func_call')
            supports_provider_reported_vision = bool(
                model_payload
                and (model_payload.get('supports_image_in') is True or model_payload.get('supports_vision') is True)
            )
            if supports_provider_reported_vision or self._supports_vision(model_id):
                abilities.append('vision')
            scanned_model['abilities'] = abilities

            context_length = self._context_length_from_scan_payload(model_payload)
            if context_length is None:
                context_length = self._safe_context_length(model_id)
            if context_length is not None:
                scanned_model['context_length'] = context_length

        return scanned_model

    def _convert_messages(self, messages: typing.List[provider_message.Message]) -> list[dict]:
        """Convert LangBot messages to LiteLLM/OpenAI format."""
        req_messages = []
        for m in messages:
            msg_dict = m.dict(exclude_none=True)
            content = msg_dict.get('content')

            if isinstance(content, list):
                converted_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get('type') == 'image_base64':
                        part['image_url'] = {'url': part['image_base64']}
                        part['type'] = 'image_url'
                        del part['image_base64']
                    # OpenAI-compatible chat models reject non-image file parts
                    # (audio/document base64 or url). These originate from Voice /
                    # File attachments — including ones replayed from conversation
                    # history — and the agent already accesses their bytes via the
                    # sandbox. Drop them from the model payload to avoid
                    # "Invalid user message ... invalid content type=file_base64".
                    if isinstance(part, dict) and part.get('type') in ('file_base64', 'file_url'):
                        continue
                    converted_parts.append(part)
                msg_dict['content'] = converted_parts

            req_messages.append(msg_dict)

        return req_messages

    _THINK_PATTERNS: tuple[str, ...] = (
        r'^\s*(?:(?!<think>).)*?</think>\s*',
        r'^\s*(?:(?!CRETIRE_REASONING_BEGINk).)*?CRETIRE_REASONING_ENDk\s*',
        r'<think>.*?</think>',
        r'CRETIRE_REASONING_BEGINk.*?CRETIRE_REASONING_ENDk',
    )

    @classmethod
    def _strip_think(cls, content: str) -> str:
        """Strip chain-of-thought blocks from ``content``."""
        if not content:
            return content

        import re

        for pattern in cls._THINK_PATTERNS:
            content = re.sub(pattern, '', content, flags=re.DOTALL)
        return content.strip()

    def _process_thinking_content(self, content: str, reasoning_content: str | None, remove_think: bool) -> str:
        """Process thinking/reasoning content.

        Args:
            content: The main content from response
            reasoning_content: Separate reasoning content from model
            remove_think: If True, remove thinking markers; if False, preserve them

        Returns:
            Processed content string
        """
        if remove_think and content:
            content = self._strip_think(content)

        if reasoning_content and not remove_think:
            content = f'<think>\n{reasoning_content}\n</think>\n{content or ""}'.strip()

        return content or ''

    @staticmethod
    def _normalize_usage(usage: typing.Any) -> dict:
        """Normalize a LiteLLM/OpenAI usage object into a plain token dict.

        Handles several real-world shapes returned by different upstreams:
        - object with ``prompt_tokens`` / ``completion_tokens`` / ``total_tokens`` attrs
        - dict with the same keys
        - missing ``total_tokens`` (derived from prompt + completion)
        - ``None`` / partially-populated usage (defaults to 0)
        - provider-specific token details, including cache token counters
        """

        def _plain_value(value: typing.Any) -> typing.Any:
            if value is None:
                return None
            if isinstance(value, dict):
                return {k: _plain_value(v) for k, v in value.items() if v is not None}
            if isinstance(value, (list, tuple)):
                return [_plain_value(v) for v in value]

            model_dump = getattr(value, 'model_dump', None)
            if callable(model_dump):
                try:
                    dumped = model_dump()
                    if isinstance(dumped, dict):
                        return _plain_value(dumped)
                except Exception:
                    pass

            return value

        def _usage_dict(value: typing.Any) -> dict[str, typing.Any]:
            if value is None:
                return {}
            plain = _plain_value(value)
            if isinstance(plain, dict):
                return plain

            def _is_mock_attr(attr: typing.Any) -> bool:
                return type(attr).__module__.startswith('unittest.mock')

            data: dict[str, typing.Any] = {}
            for key in (
                'prompt_tokens',
                'completion_tokens',
                'total_tokens',
                'prompt_tokens_details',
                'completion_tokens_details',
                'cache_creation_input_tokens',
                'cache_read_input_tokens',
                'input_token_details',
                'output_token_details',
            ):
                attr_value = getattr(value, key, None)
                if attr_value is not None and not _is_mock_attr(attr_value):
                    data[key] = _plain_value(attr_value)
            return data

        def _to_int(value: typing.Any) -> int:
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0

        normalized = _usage_dict(usage)

        prompt_tokens = _to_int(normalized.get('prompt_tokens'))
        completion_tokens = _to_int(normalized.get('completion_tokens'))
        total_tokens = _to_int(normalized.get('total_tokens'))

        # Some providers omit total_tokens in streaming usage; derive it.
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens

        normalized['prompt_tokens'] = prompt_tokens
        normalized['completion_tokens'] = completion_tokens
        normalized['total_tokens'] = total_tokens
        return normalized

    def _extract_usage(self, response) -> dict | None:
        """Extract usage info from a non-streaming LiteLLM response."""
        usage = getattr(response, 'usage', None)
        if usage is None:
            return None
        return self._normalize_usage(usage)

    @staticmethod
    def _as_dict(value: typing.Any) -> dict:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if hasattr(value, 'model_dump'):
            return value.model_dump()
        return {}

    def _normalize_stream_tool_calls(
        self,
        raw_tool_calls: typing.Any,
        tool_call_state: dict[int, dict[str, typing.Any]],
    ) -> list[dict] | None:
        """Fill OpenAI-style streaming tool-call deltas so MessageChunk can validate them.

        Also preserves provider_specific_fields (e.g., Gemini thought_signature) for
        round-tripping to the next request.
        """
        if not raw_tool_calls:
            return None

        normalized = []
        for fallback_index, raw_tool_call in enumerate(raw_tool_calls):
            tool_call = self._as_dict(raw_tool_call)
            index = tool_call.get('index')
            if not isinstance(index, int):
                index = fallback_index

            state = tool_call_state.setdefault(
                index,
                {
                    'id': '',
                    'type': 'function',
                    'name': '',
                    'provider_specific_fields': None,
                },
            )
            if tool_call.get('id'):
                state['id'] = tool_call['id']
            if tool_call.get('type'):
                state['type'] = tool_call['type']

            # Preserve provider_specific_fields from the raw tool call
            if 'provider_specific_fields' in tool_call:
                state['provider_specific_fields'] = tool_call['provider_specific_fields']

            function = self._as_dict(tool_call.get('function'))
            if function.get('name'):
                state['name'] = function['name']

            # Also check function-level provider_specific_fields
            if 'provider_specific_fields' in function:
                # Merge function-level into tool-level, function-level takes precedence
                func_psf = function['provider_specific_fields']
                if state['provider_specific_fields']:
                    merged = {**state['provider_specific_fields'], **func_psf}
                    state['provider_specific_fields'] = merged
                else:
                    state['provider_specific_fields'] = func_psf

            arguments = function.get('arguments')
            if arguments is None:
                arguments = ''
            elif not isinstance(arguments, str):
                arguments = str(arguments)

            # Some OpenAI-compatible providers (notably Ollama's
            # /v1/chat/completions) stream a tool-call delta with an `index` and
            # a `function` payload but never emit an OpenAI-style `id`. Without
            # an id the call used to be dropped here, so the whole tool call
            # silently vanished: a tool-only turn then yielded no content and no
            # tool call, the stream "completed" with 0 chars, and the chat
            # appeared stuck. Synthesize a stable per-index id so named-but-idless
            # tool calls survive. Providers that do send ids keep theirs.
            if not state['id'] and state['name']:
                state['id'] = f'call_{index}'

            if not state['id'] or not state['name']:
                continue

            tool_call_dict: dict[str, typing.Any] = {
                'id': state['id'],
                'type': state['type'] or 'function',
                'function': {
                    'name': state['name'],
                    'arguments': arguments,
                },
            }

            # Include provider_specific_fields if present
            if state['provider_specific_fields']:
                tool_call_dict['provider_specific_fields'] = state['provider_specific_fields']

            normalized.append(tool_call_dict)

        return normalized or None

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

        # Apply model-level extra_args first, then call-level extra_args
        if model.model_entity.extra_args:
            args.update(model.model_entity.extra_args)
        args.update(extra_args)

        if funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(funcs)
            if tools:
                args['tools'] = tools
                args.setdefault('tool_choice', 'auto')

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
        tool_call_state: dict[int, dict[str, typing.Any]] = {}
        think_state = _ThinkStripState() if remove_think else None

        try:
            response = await acompletion(**args)
            async for chunk in response:
                # Capture usage whenever a chunk carries it.
                #
                # Important: many OpenAI-compatible gateways (e.g. new-api) and
                # providers send the final usage payload in a chunk that STILL
                # contains a (empty-delta) choice, not an empty `choices` list.
                # The previous implementation only captured usage when `choices`
                # was empty, so streamed calls always recorded 0 tokens.
                # We therefore capture usage independently of `choices`, and then
                # fall through to also process any content this chunk may carry.
                if getattr(chunk, 'usage', None):
                    usage_info = self._normalize_usage(chunk.usage)
                    if query is not None:
                        if query.variables is None:
                            query.variables = {}
                        query.variables[requester.STREAM_USAGE_QUERY_VARIABLE] = usage_info

                if not hasattr(chunk, 'choices') or not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta.model_dump() if hasattr(choice, 'delta') else {}
                finish_reason = getattr(choice, 'finish_reason', None)

                if 'role' in delta and delta['role']:
                    role = delta['role']

                delta_content = delta.get('content', '')
                reasoning_content = delta.get('reasoning_content', '')

                # Handle reasoning_content based on remove_think flag
                if reasoning_content:
                    if remove_think:
                        # Skip reasoning content when remove_think is True
                        chunk_idx += 1
                        continue
                    else:
                        # Use reasoning_content as the displayed content
                        delta_content = reasoning_content

                if think_state is not None and delta_content:
                    delta_content = think_state.feed(delta_content)
                    if not delta_content:
                        chunk_idx += 1
                        continue

                tool_calls = self._normalize_stream_tool_calls(delta.get('tool_calls'), tool_call_state)

                if chunk_idx == 0 and not delta_content and not tool_calls:
                    chunk_idx += 1
                    continue

                chunk_data: dict[str, typing.Any] = {
                    'role': role,
                    'content': delta_content if delta_content else None,
                    'tool_calls': tool_calls,
                    'is_final': bool(finish_reason),
                }

                # Preserve provider_specific_fields from delta (e.g., Gemini thought_signatures)
                if delta.get('provider_specific_fields'):
                    chunk_data['provider_specific_fields'] = delta['provider_specific_fields']

                chunk_data = {k: v for k, v in chunk_data.items() if v is not None}
                yield provider_message.MessageChunk(**chunk_data)
                chunk_idx += 1

            if think_state is not None:
                pending_content = think_state.flush()
                if pending_content:
                    yield provider_message.MessageChunk(
                        role=role,
                        content=pending_content,
                        is_final=True,
                    )

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

            # LiteLLM returns response.data entries either as objects with an
            # `.embedding` attribute or as plain dicts (many OpenAI-compatible
            # gateways, e.g. new-api, yield dict-shaped entries). Handle both.
            embeddings = [d['embedding'] if isinstance(d, dict) else d.embedding for d in response.data]
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

        top_n = min(len(documents), 64)

        provider = self._get_custom_llm_provider()

        try:
            # LiteLLM's rerank API does not support the `openai` provider
            # (litellm/rerank_api/main.py raises "Unsupported provider: openai").
            # OpenAI-compatible gateways (newapi / one-api / vLLM / Xinference, etc.)
            # expose the standard Jina/Cohere-style POST /v1/rerank endpoint, so
            # call it directly over HTTP for openai-compatible (or unspecified) providers.
            if provider in (None, '', 'openai'):
                results = await self._invoke_rerank_openai_compatible(
                    model_name=model.model_entity.name,
                    query=query,
                    documents=documents,
                    api_key=api_key,
                    top_n=top_n,
                    extra_args={**(model.model_entity.extra_args or {}), **extra_args},
                )
            else:
                args = {
                    'model': model_name,
                    'query': query,
                    'documents': documents,
                    'api_key': api_key,
                    'top_n': top_n,
                }
                self._build_common_args(args, include_retry_params=False)

                if model.model_entity.extra_args:
                    args.update(model.model_entity.extra_args)

                args.update(extra_args)

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

        except errors.RequesterError:
            raise
        except Exception as e:
            self._handle_litellm_error(e)

    async def _invoke_rerank_openai_compatible(
        self,
        model_name: str,
        query: str,
        documents: typing.List[str],
        api_key: str,
        top_n: int,
        extra_args: dict[str, typing.Any] = {},
    ) -> typing.List[dict]:
        """Call the standard Jina/Cohere-style POST /v1/rerank endpoint over HTTP.

        Used for OpenAI-compatible gateways where litellm.arerank rejects the
        `openai` provider. Returns the same shape as the litellm path:
        a list of {'index': int, 'relevance_score': float}.
        """
        import httpx

        base_url = (self.requester_cfg.get('base_url') or '').rstrip('/')
        if not base_url:
            raise errors.RequesterError('Base URL required for rerank')

        timeout = self.requester_cfg.get('timeout', 120)

        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        payload: dict[str, typing.Any] = {
            'model': model_name,
            'query': query,
            'documents': documents,
            'top_n': top_n,
        }
        if extra_args:
            payload.update(extra_args)

        rerank_url = f'{base_url}/rerank'

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(rerank_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            body = ''
            try:
                body = e.response.text
            except Exception:
                pass
            raise errors.RequesterError(f'rerank 请求失败 (HTTP {e.response.status_code}): {body or str(e)}')
        except httpx.HTTPError as e:
            raise errors.RequesterError(f'rerank 连接错误: {str(e)}')

        raw_results = data.get('results', []) if isinstance(data, dict) else []
        results = []
        for r in raw_results:
            results.append(
                {
                    'index': r.get('index', 0),
                    'relevance_score': r.get('relevance_score', r.get('score', 0.0)) or 0.0,
                }
            )

        return results

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

                models.append(self._enrich_scanned_model(model_id, item))

            models.sort(key=lambda x: (x['type'] != 'llm', x['name'].lower()))

            return {'models': models}

        except httpx.HTTPStatusError as e:
            raise errors.RequesterError(f'Model scan failed: {e.response.status_code}')
        except httpx.TimeoutException:
            raise errors.RequesterError('Model scan timeout')
        except Exception as e:
            raise errors.RequesterError(f'Model scan error: {str(e)}')
