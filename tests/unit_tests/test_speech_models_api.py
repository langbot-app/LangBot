from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence.model import ModelProvider, ASRModel, TTSModel
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.modelmgr.requester import RuntimeProvider, RuntimeASRModel, RuntimeTTSModel
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester


class TestSpeechModels(unittest.IsolatedAsyncioTestCase):
    async def test_model_manager_asr_and_tts_cache_and_get(self):
        ap = Mock()
        ap.logger = Mock()
        ap.workspace_service = Mock()
        ap.workspace_service.get_execution_binding = AsyncMock(
            return_value=Mock(
                instance_uuid='inst-1',
                workspace_uuid='ws-1',
                placement_generation=1,
            )
        )
        mgr = ModelManager(ap)

        context = ExecutionContext(
            instance_uuid='inst-1',
            workspace_uuid='ws-1',
            placement_generation=1,
        )

        provider_entity = ModelProvider(
            uuid='prov-1',
            name='Test Provider',
            requester='openai',
            base_url='https://api.openai.com/v1',
            api_keys=['sk-test'],
            workspace_uuid='ws-1',
        )
        runtime_provider = RuntimeProvider(
            execution_context=context,
            provider_entity=provider_entity,
            token_mgr=Mock(),
            requester=Mock(),
        )

        asr_entity = ASRModel(
            uuid='asr-1',
            name='whisper-1',
            provider_uuid='prov-1',
            workspace_uuid='ws-1',
        )
        tts_entity = TTSModel(
            uuid='tts-1',
            name='tts-1',
            provider_uuid='prov-1',
            workspace_uuid='ws-1',
        )

        runtime_asr = await mgr.load_asr_model_with_provider(context, asr_entity, runtime_provider)
        await mgr.cache_asr_model(context, runtime_asr)

        runtime_tts = await mgr.load_tts_model_with_provider(context, tts_entity, runtime_provider)
        await mgr.cache_tts_model(context, runtime_tts)

        retrieved_asr = await mgr.get_asr_model_by_uuid(context, 'asr-1')
        self.assertIsNotNone(retrieved_asr)
        self.assertEqual(retrieved_asr.model_entity.uuid, 'asr-1')
        self.assertEqual(retrieved_asr.model_entity.name, 'whisper-1')

        retrieved_tts = await mgr.get_tts_model_by_uuid(context, 'tts-1')
        self.assertIsNotNone(retrieved_tts)
        self.assertEqual(retrieved_tts.model_entity.uuid, 'tts-1')
        self.assertEqual(retrieved_tts.model_entity.name, 'tts-1')

        await mgr.remove_asr_model(context, 'asr-1')
        with self.assertRaises(ValueError):
            await mgr.get_asr_model_by_uuid(context, 'asr-1')

        await mgr.remove_tts_model(context, 'tts-1')
        with self.assertRaises(ValueError):
            await mgr.get_tts_model_by_uuid(context, 'tts-1')

    async def test_litellm_requester_invoke_asr(self):
        ap = Mock()
        requester = LiteLLMRequester(ap, {'base_url': 'https://api.openai.com/v1'})

        context = ExecutionContext(
            instance_uuid='inst-1',
            workspace_uuid='ws-1',
            placement_generation=1,
        )

        provider_entity = ModelProvider(
            uuid='prov-1',
            name='OpenAI',
            requester='openai',
            base_url='https://api.openai.com/v1',
            api_keys=['sk-test-key'],
            workspace_uuid='ws-1',
        )
        runtime_provider = RuntimeProvider(
            execution_context=context,
            provider_entity=provider_entity,
            token_mgr=Mock(get_token=Mock(return_value='sk-test-key')),
            requester=requester,
        )
        asr_entity = ASRModel(
            uuid='asr-1',
            name='whisper-1',
            provider_uuid='prov-1',
            workspace_uuid='ws-1',
        )
        runtime_asr = RuntimeASRModel(
            execution_context=context,
            model_entity=asr_entity,
            provider=runtime_provider,
        )

        mock_resp = Mock(text='Hello world transcription')

        with patch('langbot.pkg.provider.modelmgr.requesters.litellmchat.atranscription', new_callable=AsyncMock) as mock_atranscription:
            mock_atranscription.return_value = mock_resp

            result = await requester.invoke_asr(
                model=runtime_asr,
                audio=b'fake-wav-bytes',
                mime='audio/wav',
            )

            self.assertEqual(result, 'Hello world transcription')
            mock_atranscription.assert_called_once()
            call_kwargs = mock_atranscription.call_args[1]
            self.assertEqual(call_kwargs['model'], 'whisper-1')
            self.assertEqual(call_kwargs['api_key'], 'sk-test-key')
            self.assertEqual(call_kwargs['api_base'], 'https://api.openai.com/v1')
            self.assertEqual(call_kwargs['file'], ('audio.wav', b'fake-wav-bytes', 'audio/wav'))

    async def test_litellm_requester_invoke_tts(self):
        ap = Mock()
        requester = LiteLLMRequester(ap, {})

        context = ExecutionContext(
            instance_uuid='inst-1',
            workspace_uuid='ws-1',
            placement_generation=1,
        )

        provider_entity = ModelProvider(
            uuid='prov-1',
            name='OpenAI',
            requester='openai',
            base_url='https://api.openai.com/v1',
            api_keys=['sk-test-key'],
            workspace_uuid='ws-1',
        )
        runtime_provider = RuntimeProvider(
            execution_context=context,
            provider_entity=provider_entity,
            token_mgr=Mock(get_token=Mock(return_value='sk-test-key')),
            requester=requester,
        )
        tts_entity = TTSModel(
            uuid='tts-1',
            name='tts-1',
            provider_uuid='prov-1',
            workspace_uuid='ws-1',
            extra_args={'voice': 'alloy'},
        )
        runtime_tts = RuntimeTTSModel(
            execution_context=context,
            model_entity=tts_entity,
            provider=runtime_provider,
        )

        mock_resp = Mock(content=b'fake-mp3-bytes', spec=['content'])

        with patch('langbot.pkg.provider.modelmgr.requesters.litellmchat.aspeech', new_callable=AsyncMock) as mock_aspeech:
            mock_aspeech.return_value = mock_resp

            content, mime = await requester.invoke_tts(
                model=runtime_tts,
                text='Hello, world!',
                extra_args={'voice': 'alloy', 'response_format': 'mp3'},
            )

            self.assertEqual(content, b'fake-mp3-bytes')
            self.assertEqual(mime, 'audio/mpeg')
            mock_aspeech.assert_called_once()
            call_kwargs = mock_aspeech.call_args[1]
            self.assertEqual(call_kwargs['model'], 'tts-1')
            self.assertEqual(call_kwargs['input'], 'Hello, world!')
            self.assertEqual(call_kwargs['voice'], 'alloy')
            self.assertEqual(call_kwargs['response_format'], 'mp3')
            self.assertEqual(call_kwargs['api_key'], 'sk-test-key')

        # Test without voice configured
        tts_entity_no_voice = TTSModel(
            uuid='tts-2',
            name='CosyVoice2',
            provider_uuid='prov-1',
            workspace_uuid='ws-1',
            extra_args={},
        )
        runtime_tts_no_voice = RuntimeTTSModel(
            execution_context=context,
            model_entity=tts_entity_no_voice,
            provider=runtime_provider,
        )
        with patch('langbot.pkg.provider.modelmgr.requesters.litellmchat.aspeech', new_callable=AsyncMock) as mock_aspeech_no_voice:
            mock_aspeech_no_voice.return_value = mock_resp
            await requester.invoke_tts(
                model=runtime_tts_no_voice,
                text='Hello without voice',
                extra_args={},
            )
            mock_aspeech_no_voice.assert_called_once()
            call_kwargs_no_voice = mock_aspeech_no_voice.call_args[1]
            self.assertNotIn('voice', call_kwargs_no_voice)

    async def test_init_temporary_runtime_tts_model_by_provider_uuid(self):
        ap = Mock()
        ap.logger = Mock()
        ap.workspace_service = Mock()
        ap.workspace_service.get_execution_binding = AsyncMock(
            return_value=Mock(
                instance_uuid='inst-1',
                workspace_uuid='ws-1',
                placement_generation=1,
            )
        )
        ap.persistence_mgr = Mock()
        saved_prov = ModelProvider(
            uuid='prov-1',
            name='Test Provider',
            requester='new-api-chat-completions',
            base_url='https://api.openai.com/v1',
            api_keys=['sk-test'],
            workspace_uuid='ws-1',
        )
        ap.persistence_mgr.execute_async = AsyncMock(return_value=Mock(first=Mock(return_value=saved_prov)))

        mgr = ModelManager(ap)
        context = ExecutionContext(
            instance_uuid='inst-1',
            workspace_uuid='ws-1',
            placement_generation=1,
        )

        with patch.object(mgr, '_build_provider', new_callable=AsyncMock) as mock_build_prov:
            mock_runtime_prov = Mock(provider_entity=saved_prov, execution_context=context)
            mock_build_prov.return_value = mock_runtime_prov

            model = await mgr.init_temporary_runtime_tts_model(
                context,
                {
                    'name': 'gpt-4o-mini-tts',
                    'provider_uuid': 'prov-1',
                    'extra_args': {'voice': 'alloy'},
                },
            )

            self.assertEqual(model.name, 'gpt-4o-mini-tts')
            self.assertEqual(model.uuid, '')
            self.assertEqual(model.extra_args, {'voice': 'alloy'})
            mock_build_prov.assert_called_once()

    def test_litellm_requester_infer_model_type_speech(self):
        req = LiteLLMRequester('openai', {'base_url': 'https://api.openai.com/v1'})
        self.assertEqual(req._infer_model_type('whisper-1'), 'asr')
        self.assertEqual(req._infer_model_type('FunAudioLLM/SenseVoiceSmall'), 'asr')
        self.assertEqual(req._infer_model_type('tts-1'), 'tts')
        self.assertEqual(req._infer_model_type('tts-1-hd'), 'tts')
        self.assertEqual(req._infer_model_type('FunAudioLLM/CosyVoice2-0.5B'), 'tts')
        self.assertEqual(req._infer_model_type('text-embedding-3-small'), 'embedding')
        self.assertEqual(req._infer_model_type('bge-reranker-v2-m3'), 'rerank')
        self.assertEqual(req._infer_model_type('gpt-4o'), 'llm')

