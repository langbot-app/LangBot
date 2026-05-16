"""Tests for OllamaChatCompletions requester.

Tests model inference, payload construction, and error handling.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from langbot.pkg.provider.modelmgr.errors import RequesterError


class TestOllamaRequesterConfig:
    """Tests for default config."""

    def test_default_config_values(self):
        """Check default_config."""
        from langbot.pkg.provider.modelmgr.requesters.ollamachat import OllamaChatCompletions

        assert OllamaChatCompletions.default_config['base_url'] == 'http://127.0.0.1:11434'
        assert OllamaChatCompletions.default_config['timeout'] == 120

    def test_config_override(self):
        """Config can override defaults."""
        from langbot.pkg.provider.modelmgr.requesters.ollamachat import OllamaChatCompletions

        mock_app = MagicMock()
        req = OllamaChatCompletions(mock_app, {
            'base_url': 'http://custom.ollama:11434',
            'timeout': 300,
        })

        assert req.requester_cfg['base_url'] == 'http://custom.ollama:11434'
        assert req.requester_cfg['timeout'] == 300


class TestOllamaInferModelType:
    """Tests for _infer_model_type pure function."""

    @pytest.fixture
    def requester(self):
        from langbot.pkg.provider.modelmgr.requesters.ollamachat import OllamaChatCompletions

        return OllamaChatCompletions(MagicMock(), {})

    def test_infer_embedding_from_name(self, requester):
        """Embedding keywords return 'embedding'."""
        assert requester._infer_model_type('nomic-embed-text') == 'embedding'
        assert requester._infer_model_type('bge-large') == 'embedding'
        assert requester._infer_model_type('text-embedding') == 'embedding'

    def test_infer_llm_from_name(self, requester):
        """Non-embedding keywords return 'llm'."""
        assert requester._infer_model_type('llama2') == 'llm'
        assert requester._infer_model_type('mistral') == 'llm'
        assert requester._infer_model_type('codellama') == 'llm'

    def test_infer_model_type_none(self, requester):
        """None model_id returns 'llm'."""
        assert requester._infer_model_type(None) == 'llm'

    def test_infer_model_type_empty(self, requester):
        """Empty model_id returns 'llm'."""
        assert requester._infer_model_type('') == 'llm'


class TestOllamaInferModelAbilities:
    """Tests for _infer_model_abilities pure function."""

    @pytest.fixture
    def requester(self):
        from langbot.pkg.provider.modelmgr.requesters.ollamachat import OllamaChatCompletions

        return OllamaChatCompletions(MagicMock(), {})

    def test_infer_vision_ability(self, requester):
        """Vision keywords add 'vision' ability."""
        item = {
            'details': {
                'family': 'llava',
            }
        }

        abilities = requester._infer_model_abilities(item, 'llava-v1.5')
        assert 'vision' in abilities

    def test_infer_vision_from_model_id(self, requester):
        """Vision keywords in model_id add 'vision' ability."""
        item = {}
        abilities = requester._infer_model_abilities(item, 'llava-7b')
        assert 'vision' in abilities

    def test_infer_func_call_ability(self, requester):
        """Tool/function keywords add 'func_call' ability."""
        item = {
            'details': {
                'families': ['tools'],
            }
        }

        abilities = requester._infer_model_abilities(item, 'model')
        assert 'func_call' in abilities

    def test_infer_no_abilities(self, requester):
        """No matching keywords returns empty abilities."""
        item = {
            'details': {
                'family': 'llama',
            }
        }

        abilities = requester._infer_model_abilities(item, 'llama-2')
        assert len(abilities) == 0

    def test_infer_multiple_abilities(self, requester):
        """Multiple keywords can add multiple abilities."""
        item = {
            'details': {
                'family': 'vision',
                'families': ['tools'],
            }
        }

        abilities = requester._infer_model_abilities(item, 'vision-tool-model')
        assert 'vision' in abilities
        assert 'func_call' in abilities


class TestOllamaMakeMessage:
    """Tests for _make_msg response parsing."""

    @pytest.fixture
    def requester(self):
        from langbot.pkg.provider.modelmgr.requesters.ollamachat import OllamaChatCompletions

        return OllamaChatCompletions(MagicMock(), {})

    def _create_ollama_response(self, content, tool_calls=None):
        """Helper to create mock ollama response."""
        import ollama

        mock_response = MagicMock(spec=ollama.ChatResponse)
        mock_message = MagicMock(spec=ollama.Message)
        mock_message.content = content
        mock_message.tool_calls = tool_calls
        mock_response.message = mock_message

        return mock_response

    @pytest.mark.asyncio
    async def test_make_msg_text_content(self, requester):
        """Text content is extracted."""
        mock_response = self._create_ollama_response('Hello world')

        result = await requester._make_msg(mock_response)

        assert result.content == 'Hello world'
        assert result.role == 'assistant'

    @pytest.mark.asyncio
    async def test_make_msg_with_tool_calls(self, requester):
        """Tool calls are parsed."""
        mock_tool_call = MagicMock()
        mock_tool_call.function = MagicMock()
        mock_tool_call.function.name = 'get_weather'
        mock_tool_call.function.arguments = {'location': 'Beijing'}

        mock_response = self._create_ollama_response('', tool_calls=[mock_tool_call])

        result = await requester._make_msg(mock_response)

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].function.name == 'get_weather'
        # Arguments should be JSON string
        assert isinstance(result.tool_calls[0].function.arguments, str)

    @pytest.mark.asyncio
    async def test_make_msg_empty_message_raises(self, requester):
        """Empty message raises ValueError."""
        mock_response = MagicMock()
        mock_response.message = None

        with pytest.raises(ValueError, match='message'):
            await requester._make_msg(mock_response)


class TestOllamaErrorHandling:
    """Tests for error handling branches."""

    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        app.tool_mgr = MagicMock()
        app.tool_mgr.generate_tools_for_openai = AsyncMock(return_value=[])
        return app

    @pytest.fixture
    def requester_with_mocked_client(self, mock_app):
        from langbot.pkg.provider.modelmgr.requesters.ollamachat import OllamaChatCompletions

        req = OllamaChatCompletions(mock_app, {})
        req.client = MagicMock()
        req.client.chat = AsyncMock()

        return req

    @pytest.fixture
    def mock_model(self):
        model = MagicMock()
        model.model_entity = MagicMock()
        model.model_entity.name = 'llama2'
        model.provider = MagicMock()
        model.provider.token_mgr = MagicMock()
        model.provider.token_mgr.get_token = MagicMock(return_value='')
        return model

    @pytest.fixture
    def mock_message(self):
        msg = MagicMock()
        msg.role = 'user'
        msg.content = 'test'
        msg.dict = MagicMock(return_value={'role': 'user', 'content': 'test'})
        return msg

    @pytest.mark.asyncio
    async def test_timeout_error(self, requester_with_mocked_client, mock_model, mock_message):
        """TimeoutError is converted to RequesterError."""
        requester_with_mocked_client.client.chat = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(RequesterError) as exc:
            await requester_with_mocked_client.invoke_llm(
                query=None,
                model=mock_model,
                messages=[mock_message],
            )

        assert '超时' in str(exc.value)


class TestOllamaScanModels:
    """Tests for scan_models method."""

    @pytest.fixture
    def mock_app(self):
        return MagicMock()

    @pytest.fixture
    def requester(self, mock_app):
        from langbot.pkg.provider.modelmgr.requesters.ollamachat import OllamaChatCompletions

        req = OllamaChatCompletions(mock_app, {
            'base_url': 'http://127.0.0.1:11434',
            'timeout': 120,
        })
        return req

    def test_requester_name_constant(self):
        """REQUESTER_NAME constant exists."""
        from langbot.pkg.provider.modelmgr.requesters.ollamachat import REQUESTER_NAME

        assert REQUESTER_NAME == 'ollama-chat'
