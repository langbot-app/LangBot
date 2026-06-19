"""
Tests for LiteLLMRequester - unified requester for chat, embedding, and rerank.

These tests verify:
- Parameter building and LiteLLM API calls
- Response processing and usage extraction
- Error handling and exception translation
- Model name building with provider prefix
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

import litellm

from langbot.pkg.provider.modelmgr.requesters import litellmchat
from langbot.pkg.provider.modelmgr import errors


class MockRuntimeModel:
    """Mock RuntimeLLMModel for testing"""

    def __init__(self, model_name: str = 'gpt-4o', api_key: str = 'test-key'):
        self.model_entity = Mock()
        self.model_entity.name = model_name
        self.model_entity.extra_args = {}
        self.provider = Mock()
        self.provider.token_mgr = Mock()
        self.provider.token_mgr.get_token = Mock(return_value=api_key)


class MockRuntimeEmbeddingModel:
    """Mock RuntimeEmbeddingModel for testing"""

    def __init__(self, model_name: str = 'text-embedding-3-small', api_key: str = 'test-key'):
        self.model_entity = Mock()
        self.model_entity.name = model_name
        self.model_entity.extra_args = {}
        self.provider = Mock()
        self.provider.token_mgr = Mock()
        self.provider.token_mgr.get_token = Mock(return_value=api_key)


class MockRuntimeRerankModel:
    """Mock RuntimeRerankModel for testing"""

    def __init__(self, model_name: str = 'cohere/rerank-english-v3.0', api_key: str = 'test-key'):
        self.model_entity = Mock()
        self.model_entity.name = model_name
        self.model_entity.extra_args = {}
        self.provider = Mock()
        self.provider.token_mgr = Mock()
        self.provider.token_mgr.get_token = Mock(return_value=api_key)


class TestBuildLiteLLMModelName:
    """Test _build_litellm_model_name method"""

    def test_no_provider_prefix(self):
        """Test model name without provider prefix"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={'custom_llm_provider': ''})
        result = requester._build_litellm_model_name('gpt-4o')
        assert result == 'gpt-4o'

    def test_with_provider_prefix(self):
        """Test model name with provider prefix"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={'custom_llm_provider': 'openai'})
        result = requester._build_litellm_model_name('gpt-4o')
        assert result == 'openai/gpt-4o'

    def test_avoid_duplicate_provider_prefix(self):
        """Test model name with an existing matching provider prefix."""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={'custom_llm_provider': 'openai'})
        result = requester._build_litellm_model_name('openai/gpt-4o')
        assert result == 'openai/gpt-4o'

    def test_override_provider(self):
        """Test override provider via parameter"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={'custom_llm_provider': 'openai'})
        result = requester._build_litellm_model_name('claude-3', custom_llm_provider='anthropic')
        assert result == 'anthropic/claude-3'


class TestExtractUsage:
    """Test _extract_usage method"""

    def test_extract_usage_with_data(self):
        """Test extraction with valid usage data"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        response = Mock()
        response.usage = Mock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50
        response.usage.total_tokens = 150

        result = requester._extract_usage(response)

        assert result['prompt_tokens'] == 100
        assert result['completion_tokens'] == 50
        assert result['total_tokens'] == 150

    def test_extract_usage_with_zero_values(self):
        """Test extraction when values are 0"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        response = Mock()
        response.usage = Mock()
        response.usage.prompt_tokens = 0
        response.usage.completion_tokens = 0
        response.usage.total_tokens = 0

        result = requester._extract_usage(response)

        assert result['prompt_tokens'] == 0
        assert result['completion_tokens'] == 0

    def test_extract_usage_without_provider_usage(self):
        """Missing provider usage is not treated as authoritative zero usage."""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        response = Mock()
        response.usage = None

        assert requester._extract_usage(response) is None


class TestNormalizeUsage:
    """Test _normalize_usage helper covering real-world usage shapes"""

    def test_none_usage(self):
        """None usage -> all zeros (no crash)"""
        result = litellmchat.LiteLLMRequester._normalize_usage(None)
        assert result == {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

    def test_dict_usage(self):
        """Usage given as a plain dict"""
        result = litellmchat.LiteLLMRequester._normalize_usage(
            {'prompt_tokens': 12, 'completion_tokens': 8, 'total_tokens': 20}
        )
        assert result == {'prompt_tokens': 12, 'completion_tokens': 8, 'total_tokens': 20}

    def test_preserves_token_details(self):
        """Provider token details such as cache counters are preserved."""
        result = litellmchat.LiteLLMRequester._normalize_usage(
            {
                'prompt_tokens': 12,
                'completion_tokens': 8,
                'total_tokens': 20,
                'prompt_tokens_details': {'cached_tokens': 7},
                'completion_tokens_details': {'reasoning_tokens': 3},
            }
        )

        assert result['prompt_tokens'] == 12
        assert result['prompt_tokens_details'] == {'cached_tokens': 7}
        assert result['completion_tokens_details'] == {'reasoning_tokens': 3}

    def test_missing_total_is_derived(self):
        """When total_tokens is absent/zero it is derived from prompt + completion"""
        usage = Mock()
        usage.prompt_tokens = 42
        usage.completion_tokens = 10
        usage.total_tokens = 0
        result = litellmchat.LiteLLMRequester._normalize_usage(usage)
        assert result['total_tokens'] == 52

    def test_partial_attrs_default_to_zero(self):
        """Missing attributes default to 0 instead of raising"""
        usage = Mock(spec=['prompt_tokens'])
        usage.prompt_tokens = 5
        result = litellmchat.LiteLLMRequester._normalize_usage(usage)
        assert result == {'prompt_tokens': 5, 'completion_tokens': 0, 'total_tokens': 5}


class TestInvokeLLMStreamUsage:
    """Regression tests for streaming token usage capture.

    Real OpenAI-compatible gateways (e.g. new-api) send the final usage payload
    in a chunk that still carries a (empty-delta) choice rather than an empty
    `choices` list. The usage must be captured regardless, otherwise streamed
    calls record 0 tokens.
    """

    def _make_chunk(self, *, content=None, tool_calls=None, finish_reason=None, usage=None, has_choice=True):
        chunk = Mock()
        if usage is not None:
            chunk.usage = usage
        else:
            chunk.usage = None
        if has_choice:
            choice = Mock()
            delta = Mock()
            delta.model_dump = Mock(return_value={'role': 'assistant', 'content': content, 'tool_calls': tool_calls})
            choice.delta = delta
            choice.finish_reason = finish_reason
            chunk.choices = [choice]
        else:
            chunk.choices = []
        return chunk

    @pytest.mark.asyncio
    async def test_stream_usage_with_nonempty_choices(self):
        """Usage chunk that still has a choice must populate _stream_usage."""
        import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(return_value=None)
        requester = litellmchat.LiteLLMRequester(ap=mock_ap, config={})
        model = MockRuntimeModel('gpt-4o', 'test-api-key')

        usage = Mock()
        usage.prompt_tokens = 24
        usage.completion_tokens = 48
        usage.total_tokens = 72

        chunks = [
            self._make_chunk(content='Hello'),
            self._make_chunk(content=None, finish_reason='stop'),
            # Final usage chunk WITH a non-empty (empty-delta) choice — the bug case.
            self._make_chunk(content=None, usage=usage, has_choice=True),
        ]

        async def _aiter(*args, **kwargs):
            for c in chunks:
                yield c

        query = Mock(spec=pipeline_query.Query)
        query.variables = {}

        messages = [provider_message.Message(role='user', content='Hi')]

        with patch.object(litellmchat, 'acompletion', new=AsyncMock(side_effect=lambda **kw: _aiter())):
            collected = []
            async for ch in requester.invoke_llm_stream(query=query, model=model, messages=messages):
                collected.append(ch)

        assert '_stream_usage' in query.variables
        assert query.variables['_stream_usage']['prompt_tokens'] == 24
        assert query.variables['_stream_usage']['completion_tokens'] == 48
        assert query.variables['_stream_usage']['total_tokens'] == 72

    @pytest.mark.asyncio
    async def test_stream_usage_with_empty_choices(self):
        """Usage chunk with empty choices list must also populate _stream_usage."""
        import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(return_value=None)
        requester = litellmchat.LiteLLMRequester(ap=mock_ap, config={})
        model = MockRuntimeModel('gpt-4o', 'test-api-key')

        usage = Mock()
        usage.prompt_tokens = 5
        usage.completion_tokens = 7
        usage.total_tokens = 12

        chunks = [
            self._make_chunk(content='Hi there'),
            self._make_chunk(content=None, finish_reason='stop'),
            self._make_chunk(usage=usage, has_choice=False),
        ]

        async def _aiter(*args, **kwargs):
            for c in chunks:
                yield c

        query = Mock(spec=pipeline_query.Query)
        query.variables = {}
        messages = [provider_message.Message(role='user', content='Hi')]

        with patch.object(litellmchat, 'acompletion', new=AsyncMock(side_effect=lambda **kw: _aiter())):
            async for _ in requester.invoke_llm_stream(query=query, model=model, messages=messages):
                pass

        assert query.variables['_stream_usage']['total_tokens'] == 12

    @pytest.mark.asyncio
    async def test_stream_tool_call_delta_missing_id_and_name(self):
        """LiteLLM may stream tool-call argument deltas with id/name set to None."""
        import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(
            return_value=[{'type': 'function', 'function': {'name': 'qa_plugin_echo'}}]
        )
        requester = litellmchat.LiteLLMRequester(ap=mock_ap, config={})
        model = MockRuntimeModel('gpt-4o', 'test-api-key')

        chunks = [
            self._make_chunk(
                tool_calls=[
                    {
                        'index': 0,
                        'id': 'call_123',
                        'type': 'function',
                        'function': {'name': 'qa_plugin_echo', 'arguments': ''},
                    }
                ]
            ),
            self._make_chunk(
                tool_calls=[
                    {
                        'index': 0,
                        'id': None,
                        'type': None,
                        'function': {'name': None, 'arguments': '{"text":'},
                    }
                ]
            ),
            self._make_chunk(
                tool_calls=[
                    {
                        'index': 0,
                        'function': {'arguments': '"plugin-tool-ok"}'},
                    }
                ]
            ),
            self._make_chunk(finish_reason='tool_calls'),
        ]

        async def _aiter(*args, **kwargs):
            for c in chunks:
                yield c

        query = Mock(spec=pipeline_query.Query)
        query.variables = {}
        messages = [provider_message.Message(role='user', content='Call the tool')]
        funcs = [Mock()]

        with patch.object(litellmchat, 'acompletion', new=AsyncMock(side_effect=lambda **kw: _aiter())):
            collected = [
                chunk
                async for chunk in requester.invoke_llm_stream(
                    query=query,
                    model=model,
                    messages=messages,
                    funcs=funcs,
                )
            ]

        tool_chunks = [chunk for chunk in collected if chunk.tool_calls]
        assert len(tool_chunks) == 3
        assert tool_chunks[1].tool_calls[0].id == 'call_123'
        assert tool_chunks[1].tool_calls[0].function.name == 'qa_plugin_echo'
        assert tool_chunks[1].tool_calls[0].function.arguments == '{"text":'
        assert tool_chunks[2].tool_calls[0].function.arguments == '"plugin-tool-ok"}'

    @pytest.mark.asyncio
    async def test_stream_tool_call_without_id_is_not_dropped(self):
        """Regression for #2261.

        Ollama's OpenAI-compatible streaming endpoint emits a tool-call delta
        carrying an ``index`` and a ``function`` payload but never an
        OpenAI-style ``id``. The requester used to drop any id-less tool call,
        so a tool-only turn yielded nothing, the stream "completed" with 0
        chars, and the chat got stuck. A stable per-index id must be
        synthesized so the tool call survives.
        """
        import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(
            return_value=[{'type': 'function', 'function': {'name': 'zotero_search_items'}}]
        )
        requester = litellmchat.LiteLLMRequester(ap=mock_ap, config={'custom_llm_provider': 'openai'})
        model = MockRuntimeModel('gpt-oss:20b', 'ollama')

        # Ollama delivers the whole tool call in a single delta, with no id.
        chunks = [
            self._make_chunk(
                tool_calls=[
                    {
                        'index': 0,
                        'function': {'name': 'zotero_search_items', 'arguments': '{"query":"hello"}'},
                    }
                ]
            ),
            self._make_chunk(finish_reason='tool_calls'),
        ]

        async def _aiter(*args, **kwargs):
            for c in chunks:
                yield c

        query = Mock(spec=pipeline_query.Query)
        query.variables = {}
        messages = [provider_message.Message(role='user', content='hello?')]
        funcs = [Mock()]

        with patch.object(litellmchat, 'acompletion', new=AsyncMock(side_effect=lambda **kw: _aiter())):
            collected = [
                chunk
                async for chunk in requester.invoke_llm_stream(
                    query=query,
                    model=model,
                    messages=messages,
                    funcs=funcs,
                )
            ]

        tool_chunks = [chunk for chunk in collected if chunk.tool_calls]
        assert len(tool_chunks) == 1, 'id-less Ollama tool call must not be dropped'
        tc = tool_chunks[0].tool_calls[0]
        assert tc.id == 'call_0'
        assert tc.function.name == 'zotero_search_items'
        assert tc.function.arguments == '{"query":"hello"}'

    @pytest.mark.asyncio
    async def test_stream_multiple_tool_calls_without_id_get_distinct_ids(self):
        """Two parallel id-less tool calls must keep distinct synthesized ids."""
        import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(
            return_value=[{'type': 'function', 'function': {'name': 'zotero_search_items'}}]
        )
        requester = litellmchat.LiteLLMRequester(ap=mock_ap, config={'custom_llm_provider': 'openai'})
        model = MockRuntimeModel('gpt-oss:20b', 'ollama')

        chunks = [
            self._make_chunk(
                tool_calls=[
                    {'index': 0, 'function': {'name': 'zotero_search_items', 'arguments': '{"q":"a"}'}},
                    {'index': 1, 'function': {'name': 'zotero_get_notes', 'arguments': '{"q":"b"}'}},
                ]
            ),
            self._make_chunk(finish_reason='tool_calls'),
        ]

        async def _aiter(*args, **kwargs):
            for c in chunks:
                yield c

        query = Mock(spec=pipeline_query.Query)
        query.variables = {}
        messages = [provider_message.Message(role='user', content='hello?')]
        funcs = [Mock()]

        with patch.object(litellmchat, 'acompletion', new=AsyncMock(side_effect=lambda **kw: _aiter())):
            collected = [
                chunk
                async for chunk in requester.invoke_llm_stream(
                    query=query,
                    model=model,
                    messages=messages,
                    funcs=funcs,
                )
            ]

        tool_chunks = [chunk for chunk in collected if chunk.tool_calls]
        assert len(tool_chunks) == 1
        ids = {tc.id for tc in tool_chunks[0].tool_calls}
        assert ids == {'call_0', 'call_1'}


class TestProcessThinkingContent:
    """Test _process_thinking_content method"""

    def test_no_thinking_markers(self):
        """Test content without thinking markers"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        result = requester._process_thinking_content('Hello world', None, remove_think=True)
        assert result == 'Hello world'

    def test_remove_thinking_markers(self):
        """Test removing thinking markers when remove_think=True"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        content = 'CRETIRE_REASONING_BEGINkLet me think...CRETIRE_REASONING_ENDk The answer is 42.'
        result = requester._process_thinking_content(content, None, remove_think=True)
        assert result == 'The answer is 42.'

    def test_preserve_thinking_markers(self):
        """Test preserving thinking markers when remove_think=False"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        content = 'CRETIRE_REASONING_BEGINkLet me think...CRETIRE_REASONING_ENDk The answer is 42.'
        result = requester._process_thinking_content(content, None, remove_think=False)
        assert 'CRETIRE_REASONING_BEGINk' in result
        assert 'The answer is 42.' in result

    def test_empty_content(self):
        """Test empty content"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        result = requester._process_thinking_content('', None, remove_think=True)
        assert result == ''


class TestBuildCommonArgs:
    """Test _build_common_args method"""

    def test_build_args_with_all_params(self):
        """Test building args with all config params"""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.openai.com/v1',
                'timeout': 60,
                'drop_params': True,
                'num_retries': 3,
                'api_version': '2024-01-01',
            },
        )

        args = {}
        requester._build_common_args(args)

        assert args['api_base'] == 'https://api.openai.com/v1'
        assert args['timeout'] == 60
        assert args['drop_params'] == True
        assert args['num_retries'] == 3
        assert args['api_version'] == '2024-01-01'

    def test_build_args_without_retry_params(self):
        """Test building args without retry params for embedding/rerank"""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.openai.com/v1',
                'timeout': 60,
                'num_retries': 3,
            },
        )

        args = {}
        requester._build_common_args(args, include_retry_params=False)

        assert args['api_base'] == 'https://api.openai.com/v1'
        assert args['timeout'] == 60
        assert 'num_retries' not in args


class TestHandleLiteLLMError:
    """Test _handle_litellm_error method"""

    def test_bad_request_error(self):
        """Test BadRequestError translation"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        # Create proper LiteLLM exception with required args
        error = litellm.BadRequestError(message='test error', model='gpt-4o', llm_provider='openai')

        with pytest.raises(errors.RequesterError) as exc_info:
            requester._handle_litellm_error(error)

        assert '请求参数错误' in str(exc_info.value)

    def test_authentication_error(self):
        """Test AuthenticationError translation"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        error = litellm.AuthenticationError(message='invalid key', model='gpt-4o', llm_provider='openai')

        with pytest.raises(errors.RequesterError) as exc_info:
            requester._handle_litellm_error(error)

        assert 'API key 无效' in str(exc_info.value)

    def test_rate_limit_error(self):
        """Test RateLimitError translation"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        error = litellm.RateLimitError(message='rate limited', model='gpt-4o', llm_provider='openai')

        with pytest.raises(errors.RequesterError) as exc_info:
            requester._handle_litellm_error(error)

        assert '请求过于频繁' in str(exc_info.value)

    def test_timeout_error(self):
        """Test Timeout translation"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        error = litellm.Timeout(message='timeout', model='gpt-4o', llm_provider='openai')

        with pytest.raises(errors.RequesterError) as exc_info:
            requester._handle_litellm_error(error)

        assert '请求超时' in str(exc_info.value)

    def test_context_window_error(self):
        """Test ContextWindowExceededError translation"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        error = litellm.ContextWindowExceededError(message='context too long', model='gpt-4o', llm_provider='openai')

        with pytest.raises(errors.RequesterError) as exc_info:
            requester._handle_litellm_error(error)

        assert '上下文长度超限' in str(exc_info.value)

    def test_unknown_error(self):
        """Test unknown error translation"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        with pytest.raises(errors.RequesterError) as exc_info:
            requester._handle_litellm_error(Exception('unknown'))

        assert '未知错误' in str(exc_info.value)


class TestInvokeLLM:
    """Test invoke_llm method"""

    @pytest.mark.asyncio
    async def test_invoke_llm_basic(self):
        """Test basic LLM invocation"""
        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(return_value=None)

        requester = litellmchat.LiteLLMRequester(
            ap=mock_ap,
            config={
                'base_url': 'https://api.openai.com/v1',
                'timeout': 60,
            },
        )

        model = MockRuntimeModel('gpt-4o', 'test-api-key')

        # Mock LiteLLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.model_dump = Mock(
            return_value={
                'role': 'assistant',
                'content': 'Hello! How can I help you?',
            }
        )
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        messages = [provider_message.Message(role='user', content='Hello')]

        # Patch acompletion at the import location
        with patch.object(litellmchat, 'acompletion', new_callable=AsyncMock, return_value=mock_response):
            result_msg, usage = await requester.invoke_llm(
                query=None,
                model=model,
                messages=messages,
            )

            assert result_msg.role == 'assistant'
            assert result_msg.content == 'Hello! How can I help you?'
            assert usage['prompt_tokens'] == 10
            assert usage['completion_tokens'] == 20

    @pytest.mark.asyncio
    async def test_invoke_llm_with_tools(self):
        """Test LLM invocation with function calling"""
        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(
            return_value=[{'type': 'function', 'function': {'name': 'get_weather'}}]
        )

        requester = litellmchat.LiteLLMRequester(ap=mock_ap, config={})

        model = MockRuntimeModel('gpt-4o', 'test-api-key')

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.model_dump = Mock(
            return_value={
                'role': 'assistant',
                'content': None,
                'tool_calls': [
                    {'id': 'call_123', 'type': 'function', 'function': {'name': 'get_weather', 'arguments': '{}'}}
                ],
            }
        )
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 10
        mock_response.usage.total_tokens = 25

        import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        messages = [provider_message.Message(role='user', content='What is the weather?')]
        # Create proper LLMTool with all required fields
        funcs = [Mock(spec=resource_tool.LLMTool)]
        funcs[0].name = 'get_weather'
        funcs[0].description = 'Get weather'

        with patch.object(litellmchat, 'acompletion', new_callable=AsyncMock, return_value=mock_response):
            result_msg, usage = await requester.invoke_llm(
                query=None,
                model=model,
                messages=messages,
                funcs=funcs,
            )

            assert result_msg.tool_calls is not None
            called_kwargs = litellmchat.acompletion.await_args.kwargs
            assert called_kwargs['tools'] == [{'type': 'function', 'function': {'name': 'get_weather'}}]
            assert called_kwargs['tool_choice'] == 'auto'

    @pytest.mark.asyncio
    async def test_build_completion_args_preserves_explicit_tool_choice(self):
        """Model extra args can override the default auto tool choice."""
        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(
            return_value=[{'type': 'function', 'function': {'name': 'get_weather'}}]
        )

        requester = litellmchat.LiteLLMRequester(ap=mock_ap, config={})
        model = MockRuntimeModel('gpt-4o', 'test-api-key')
        model.model_entity.extra_args = {'tool_choice': 'required'}

        import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        funcs = [Mock(spec=resource_tool.LLMTool)]
        messages = [provider_message.Message(role='user', content='What is the weather?')]

        args = await requester._build_completion_args(model, messages, funcs)

        assert args['tool_choice'] == 'required'

    @pytest.mark.asyncio
    async def test_invoke_llm_error_handling(self):
        """Test LLM invocation error handling"""
        mock_ap = Mock()
        mock_ap.tool_mgr = Mock()
        mock_ap.tool_mgr.generate_tools_for_openai = AsyncMock(return_value=None)

        requester = litellmchat.LiteLLMRequester(ap=mock_ap, config={})

        model = MockRuntimeModel('gpt-4o', 'test-api-key')

        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        messages = [provider_message.Message(role='user', content='Hello')]

        error = litellm.AuthenticationError(message='invalid key', model='gpt-4o', llm_provider='openai')

        with patch.object(litellmchat, 'acompletion', new_callable=AsyncMock, side_effect=error):
            with pytest.raises(errors.RequesterError) as exc_info:
                await requester.invoke_llm(
                    query=None,
                    model=model,
                    messages=messages,
                )

            assert 'API key 无效' in str(exc_info.value)


class TestInvokeEmbedding:
    """Test invoke_embedding method"""

    @pytest.mark.asyncio
    async def test_invoke_embedding_basic(self):
        """Test basic embedding invocation"""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.openai.com/v1',
            },
        )

        model = MockRuntimeEmbeddingModel('text-embedding-3-small', 'test-api-key')

        # Mock LiteLLM embedding response
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2, 0.3]),
            Mock(embedding=[0.4, 0.5, 0.6]),
        ]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 0
        mock_response.usage.total_tokens = 20

        with patch.object(litellmchat, 'aembedding', new_callable=AsyncMock, return_value=mock_response):
            embeddings, usage = await requester.invoke_embedding(
                model=model,
                input_text=['Hello', 'World'],
            )

            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2, 0.3]
            assert embeddings[1] == [0.4, 0.5, 0.6]
            assert usage['prompt_tokens'] == 20


class TestInvokeRerank:
    """Test invoke_rerank method"""

    @pytest.mark.asyncio
    async def test_invoke_rerank_basic(self):
        """Test basic rerank invocation"""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.cohere.ai',
                'custom_llm_provider': 'cohere',
            },
        )

        model = MockRuntimeRerankModel('rerank-english-v3.0', 'test-api-key')

        # Mock LiteLLM rerank response
        mock_response = Mock()
        mock_response.results = [
            {'index': 0, 'relevance_score': 0.95},
            {'index': 1, 'relevance_score': 0.3},
            {'index': 2, 'relevance_score': 0.8},
        ]

        with patch.object(litellmchat, 'arerank', new_callable=AsyncMock, return_value=mock_response):
            results = await requester.invoke_rerank(
                model=model,
                query='What is the capital of France?',
                documents=['Paris is the capital.', 'London is a city.', 'France is in Europe.'],
            )

            assert len(results) == 3
            # Scores should be normalized
            assert results[0]['index'] == 0
            assert results[0]['relevance_score'] >= 0 and results[0]['relevance_score'] <= 1

    @pytest.mark.asyncio
    async def test_invoke_rerank_normalization(self):
        """Test rerank score normalization"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={'custom_llm_provider': 'cohere'})

        model = MockRuntimeRerankModel('rerank-english-v3.0', 'test-api-key')

        # Mock response with varying scores
        mock_response = Mock()
        mock_response.results = [
            {'index': 0, 'relevance_score': 0.9},
            {'index': 1, 'relevance_score': 0.1},
        ]

        with patch.object(litellmchat, 'arerank', new_callable=AsyncMock, return_value=mock_response):
            results = await requester.invoke_rerank(
                model=model,
                query='test query',
                documents=['doc1', 'doc2'],
            )

            # After normalization: 0.9 -> 1.0, 0.1 -> 0.0
            assert results[0]['relevance_score'] == 1.0
            assert results[1]['relevance_score'] == 0.0

    @pytest.mark.asyncio
    async def test_invoke_rerank_single_document(self):
        """Test rerank with single document (no normalization needed)"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={'custom_llm_provider': 'cohere'})

        model = MockRuntimeRerankModel('rerank-english-v3.0', 'test-api-key')

        mock_response = Mock()
        mock_response.results = [
            {'index': 0, 'relevance_score': 0.5},
        ]

        with patch.object(litellmchat, 'arerank', new_callable=AsyncMock, return_value=mock_response):
            results = await requester.invoke_rerank(
                model=model,
                query='test query',
                documents=['doc1'],
            )

            assert len(results) == 1
            # Single score stays as is (min==max, no normalization)
            assert results[0]['relevance_score'] == 0.5

    @pytest.mark.asyncio
    async def test_invoke_rerank_openai_compatible_http(self):
        """OpenAI-compatible gateways (newapi/one-api/vLLM) must use the HTTP /v1/rerank
        endpoint instead of litellm.arerank, which rejects the 'openai' provider."""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://gateway.example.com/v1',
                'custom_llm_provider': 'openai',
            },
        )

        model = MockRuntimeRerankModel('bge-reranker-v2-m3', 'test-api-key')

        # Mock the standard Jina/Cohere-style /v1/rerank HTTP response
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json = Mock(
            return_value={
                'results': [
                    {'index': 0, 'relevance_score': 0.9},
                    {'index': 1, 'relevance_score': 0.1},
                ]
            }
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch('httpx.AsyncClient', return_value=mock_client):
            # arerank must NOT be called on the openai-compatible path
            with patch.object(
                litellmchat,
                'arerank',
                new_callable=AsyncMock,
                side_effect=AssertionError('arerank must not be used for openai-compatible provider'),
            ):
                results = await requester.invoke_rerank(
                    model=model,
                    query='test query',
                    documents=['doc1', 'doc2'],
                )

        # Hit the standard rerank endpoint
        called_url = mock_client.post.call_args[0][0]
        assert called_url == 'https://gateway.example.com/v1/rerank'
        # Payload carries the raw model name, query and documents
        payload = mock_client.post.call_args[1]['json']
        assert payload['model'] == 'bge-reranker-v2-m3'
        assert payload['query'] == 'test query'
        assert payload['documents'] == ['doc1', 'doc2']
        # Scores normalized: 0.9 -> 1.0, 0.1 -> 0.0
        assert results[0]['relevance_score'] == 1.0
        assert results[1]['relevance_score'] == 0.0

    @pytest.mark.asyncio
    async def test_invoke_rerank_openai_compatible_score_alias(self):
        """Some gateways return 'score' instead of 'relevance_score'; both must work."""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://gateway.example.com/v1',
                'custom_llm_provider': 'openai',
            },
        )

        model = MockRuntimeRerankModel('bge-reranker-v2-m3', 'test-api-key')

        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json = Mock(
            return_value={
                'results': [
                    {'index': 0, 'score': 0.8},
                    {'index': 1, 'score': 0.2},
                ]
            }
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch('httpx.AsyncClient', return_value=mock_client):
            results = await requester.invoke_rerank(
                model=model,
                query='test query',
                documents=['doc1', 'doc2'],
            )

        assert results[0]['relevance_score'] == 1.0
        assert results[1]['relevance_score'] == 0.0


class TestConvertMessages:
    """Test _convert_messages method"""

    def test_convert_simple_message(self):
        """Test converting simple text message"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        messages = [provider_message.Message(role='user', content='Hello')]
        result = requester._convert_messages(messages)

        assert len(result) == 1
        assert result[0]['role'] == 'user'
        assert result[0]['content'] == 'Hello'

    def test_convert_message_with_image_base64(self):
        """Test converting message with image_base64 content"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        messages = [
            provider_message.Message(
                role='user',
                content=[
                    {'type': 'text', 'text': 'What is in this image?'},
                    {'type': 'image_base64', 'image_base64': 'data:image/png;base64,abc123'},
                ],
            )
        ]
        result = requester._convert_messages(messages)

        assert len(result) == 1
        content = result[0]['content']
        assert isinstance(content, list)
        # Check image_base64 converted to image_url
        image_part = [p for p in content if p.get('type') == 'image_url'][0]
        assert 'image_url' in image_part
        assert image_part['image_url']['url'] == 'data:image/png;base64,abc123'

    def test_convert_message_with_multiple_text_parts(self):
        """Test converting message with multiple text parts (LiteLLM handles this)"""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        messages = [
            provider_message.Message(
                role='user',
                content=[
                    {'type': 'text', 'text': 'Hello'},
                    {'type': 'text', 'text': 'World'},
                ],
            )
        ]
        result = requester._convert_messages(messages)

        assert len(result) == 1
        # LiteLLM handles multiple text parts, we pass them through
        assert isinstance(result[0]['content'], list)


class TestScanModels:
    """Test scan_models method"""

    @pytest.mark.asyncio
    async def test_scan_models_basic(self):
        """Test basic model scanning"""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.openai.com/v1',
                'timeout': 60,
            },
        )

        # Mock httpx response
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                'data': [
                    {'id': 'gpt-4o'},
                    {'id': 'text-embedding-3-small'},
                    {'id': 'gpt-3.5-turbo'},
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=Mock())
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await requester.scan_models(api_key='test-key')

            assert 'models' in result
            assert len(result['models']) == 3
            # Check LLM models are first
            assert result['models'][0]['type'] == 'llm'
            # Check embedding model is detected
            embedding_models = [m for m in result['models'] if m['type'] == 'embedding']
            assert len(embedding_models) == 1

    @pytest.mark.asyncio
    async def test_scan_models_enriches_llm_abilities_and_context_length(self):
        """Scanned LLM models get LiteLLM-derived abilities and context length."""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.openai.com/v1',
                'timeout': 60,
            },
        )
        requester._supports_function_calling = Mock(side_effect=lambda model_id: model_id == 'gpt-4o')
        requester._supports_vision = Mock(side_effect=lambda model_id: model_id == 'gpt-4o')
        requester._safe_context_length = Mock(side_effect=lambda model_id: 128000 if model_id == 'gpt-4o' else None)

        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                'data': [
                    {'id': 'gpt-4o'},
                    {'id': 'text-embedding-3-small'},
                    {'id': 'bge-reranker-v2'},
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=Mock())
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await requester.scan_models(api_key='test-key')

        by_id = {model['id']: model for model in result['models']}
        assert by_id['gpt-4o']['abilities'] == ['func_call', 'vision']
        assert by_id['gpt-4o']['context_length'] == 128000
        assert by_id['text-embedding-3-small']['type'] == 'embedding'
        assert by_id['bge-reranker-v2']['type'] == 'rerank'

    @pytest.mark.asyncio
    async def test_scan_models_prefers_context_length_from_provider_payload(self):
        """Provider-supplied context_length is preserved before LiteLLM metadata fallback."""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.moonshot.cn/v1',
                'timeout': 60,
            },
        )
        requester._supports_function_calling = Mock(return_value=False)
        requester._supports_vision = Mock(return_value=False)
        requester._safe_context_length = Mock(return_value=None)

        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                'data': [
                    {'id': 'moonshot-v1-128k', 'context_length': 131072},
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=Mock())
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await requester.scan_models(api_key='test-key')

        assert result['models'][0]['context_length'] == 131072
        requester._safe_context_length.assert_not_called()

    def test_safe_context_length_tries_moonshot_metadata_alias(self):
        """OpenAI-compatible Moonshot endpoints still use Moonshot metadata for context windows."""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.moonshot.cn/v1',
                'custom_llm_provider': 'openai',
            },
        )

        with patch.object(litellmchat.litellm, 'get_model_info') as mock_get_model_info:
            mock_get_model_info.side_effect = (
                lambda model: {'max_input_tokens': 131072} if model == 'moonshot/moonshot-v1-128k' else {}
            )

            assert requester._safe_context_length('moonshot-v1-128k') == 131072

    def test_safe_context_length_uses_litellm_max_input_tokens(self):
        """LiteLLM max_output_tokens must not be treated as the context window."""
        requester = litellmchat.LiteLLMRequester(ap=Mock(), config={})

        with patch.object(litellmchat.litellm, 'get_model_info') as mock_get_model_info:
            mock_get_model_info.return_value = {
                'max_input_tokens': 128000,
                'max_output_tokens': 16384,
                'max_tokens': 16384,
            }

            assert requester._safe_context_length('gpt-4o') == 128000

    def test_litellm_bool_helper_tries_moonshot_metadata_alias(self):
        """OpenAI-compatible Moonshot endpoints still use Moonshot metadata for abilities."""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.moonshot.cn/v1',
                'custom_llm_provider': 'openai',
            },
        )

        with patch.object(litellmchat.litellm, 'supports_function_calling') as mock_supports_function_calling:
            mock_supports_function_calling.side_effect = (
                lambda model, custom_llm_provider=None: model == 'moonshot/kimi-k2.6' and custom_llm_provider is None
            )

            assert requester._supports_function_calling('kimi-k2.6') is True

    @pytest.mark.asyncio
    async def test_scan_models_uses_provider_payload_for_vision_ability(self):
        """Provider-supplied vision support is used when scanning models."""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.moonshot.cn/v1',
                'timeout': 60,
            },
        )
        requester._supports_function_calling = Mock(return_value=False)
        requester._supports_vision = Mock(return_value=False)
        requester._safe_context_length = Mock(return_value=None)

        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                'data': [
                    {
                        'id': 'moonshot-v1-128k-vision-preview',
                        'supports_image_in': True,
                    },
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=Mock())
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await requester.scan_models(api_key='test-key')

        assert result['models'][0]['abilities'] == ['vision']

    def test_safe_context_length_falls_back_for_deepseek_v4_models(self):
        """DeepSeek V4 API ids have a known 1M context even before LiteLLM maps them."""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': 'https://api.deepseek.com',
                'custom_llm_provider': 'deepseek',
            },
        )

        with patch.object(litellmchat.litellm, 'get_model_info', side_effect=Exception('not mapped')):
            assert requester._safe_context_length('deepseek-v4-pro') == 1_000_000
            assert requester._safe_context_length('deepseek-v4-flash') == 1_000_000

    @pytest.mark.asyncio
    async def test_scan_models_no_base_url(self):
        """Test scan_models without base_url raises error"""
        requester = litellmchat.LiteLLMRequester(
            ap=Mock(),
            config={
                'base_url': '',
            },
        )

        with pytest.raises(errors.RequesterError) as exc_info:
            await requester.scan_models()

        assert 'Base URL required' in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
