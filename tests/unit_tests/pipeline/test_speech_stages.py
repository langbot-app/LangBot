from __future__ import annotations

import base64
import io
from unittest.mock import AsyncMock, Mock
import wave

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import pytest

from langbot.pkg.pipeline.entities import ResultType
from langbot.pkg.pipeline.speech import speech as speech_module


def _create_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\x00' * 3200)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_stt_disabled_continues(mock_app, sample_query):
    sample_query.pipeline_config = {
        'speech': {
            'speech-to-text': {
                'enable': False,
                'model': 'stt-model-uuid',
            }
        }
    }
    stage = speech_module.SpeechToTextStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'SpeechToTextStage')
    assert result.result_type == ResultType.CONTINUE


@pytest.mark.asyncio
async def test_stt_no_voice_continues(mock_app, sample_query):
    sample_query.pipeline_config = {
        'speech': {
            'speech-to-text': {
                'enable': True,
                'model': 'stt-model-uuid',
            }
        }
    }
    sample_query.message_chain = platform_message.MessageChain([platform_message.Plain(text='hello')])
    stage = speech_module.SpeechToTextStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'SpeechToTextStage')
    assert result.result_type == ResultType.CONTINUE


@pytest.mark.asyncio
async def test_stt_max_duration_exceeded_notify_stops(mock_app, sample_query):
    sample_query.pipeline_config = {
        'speech': {
            'speech-to-text': {
                'enable': True,
                'model': 'stt-model-uuid',
                'max-duration': 30,
                'on-failure': 'notify',
            }
        }
    }
    sample_query.message_chain = platform_message.MessageChain(
        [platform_message.Voice(base64='dummy', length=45)]
    )
    stage = speech_module.SpeechToTextStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'SpeechToTextStage')
    assert result.result_type == ResultType.INTERRUPT
    assert result.user_notice == 'Voice message exceeds maximum duration.'


@pytest.mark.asyncio
async def test_stt_max_duration_exceeded_ignore_continues(mock_app, sample_query):
    sample_query.pipeline_config = {
        'speech': {
            'speech-to-text': {
                'enable': True,
                'model': 'stt-model-uuid',
                'max-duration': 30,
                'on-failure': 'ignore',
            }
        }
    }
    sample_query.message_chain = platform_message.MessageChain(
        [platform_message.Voice(base64='dummy', length=45)]
    )
    stage = speech_module.SpeechToTextStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'SpeechToTextStage')
    assert result.result_type == ResultType.CONTINUE


@pytest.mark.asyncio
async def test_stt_success_replaces_voice(mock_app, sample_query):
    wav_bytes = _create_wav_bytes()
    b64_str = base64.b64encode(wav_bytes).decode('ascii')
    sample_query.pipeline_config = {
        'speech': {
            'speech-to-text': {
                'enable': True,
                'model': 'stt-model-uuid',
                'keep-original-voice': False,
                'max-duration': 60,
            }
        }
    }
    sample_query.message_chain = platform_message.MessageChain([platform_message.Voice(base64=b64_str)])

    mock_stt_model = Mock()
    mock_stt_model.execution_context = Mock()
    mock_stt_model.provider = Mock()
    mock_stt_model.provider.invoke_stt = AsyncMock(return_value=Mock(text='Transcribed voice message'))
    mock_app.model_mgr.get_stt_model_by_uuid = AsyncMock(return_value=mock_stt_model)

    stage = speech_module.SpeechToTextStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'SpeechToTextStage')

    assert result.result_type == ResultType.CONTINUE
    assert sample_query.variables['_input_was_voice'] is True
    assert sample_query.variables['voice_transcript'] == 'Transcribed voice message'
    assert len(sample_query.message_chain) == 1
    assert isinstance(sample_query.message_chain[0], platform_message.Plain)
    assert sample_query.message_chain[0].text == 'Transcribed voice message'


@pytest.mark.asyncio
async def test_stt_success_keep_original_voice(mock_app, sample_query):
    wav_bytes = _create_wav_bytes()
    b64_str = base64.b64encode(wav_bytes).decode('ascii')
    sample_query.pipeline_config = {
        'speech': {
            'speech-to-text': {
                'enable': True,
                'model': 'stt-model-uuid',
                'keep-original-voice': True,
                'max-duration': 60,
            }
        }
    }
    sample_query.message_chain = platform_message.MessageChain([platform_message.Voice(base64=b64_str)])

    mock_stt_model = Mock()
    mock_stt_model.execution_context = Mock()
    mock_stt_model.provider = Mock()
    mock_stt_model.provider.invoke_stt = AsyncMock(return_value=Mock(text='Transcribed voice message'))
    mock_app.model_mgr.get_stt_model_by_uuid = AsyncMock(return_value=mock_stt_model)

    stage = speech_module.SpeechToTextStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'SpeechToTextStage')

    assert result.result_type == ResultType.CONTINUE
    assert len(sample_query.message_chain) == 2
    assert isinstance(sample_query.message_chain[0], platform_message.Voice)
    assert isinstance(sample_query.message_chain[1], platform_message.Plain)
    assert sample_query.message_chain[1].text == 'Transcribed voice message'


@pytest.mark.asyncio
async def test_stt_failure_notify_stops(mock_app, sample_query):
    wav_bytes = _create_wav_bytes()
    b64_str = base64.b64encode(wav_bytes).decode('ascii')
    sample_query.pipeline_config = {
        'speech': {
            'speech-to-text': {
                'enable': True,
                'model': 'stt-model-uuid',
                'on-failure': 'notify',
            }
        }
    }
    sample_query.message_chain = platform_message.MessageChain([platform_message.Voice(base64=b64_str)])

    mock_stt_model = Mock()
    mock_stt_model.execution_context = Mock()
    mock_stt_model.provider = Mock()
    mock_stt_model.provider.invoke_stt = AsyncMock(side_effect=RuntimeError('Transcription API error'))
    mock_app.model_mgr.get_stt_model_by_uuid = AsyncMock(return_value=mock_stt_model)

    stage = speech_module.SpeechToTextStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'SpeechToTextStage')

    assert result.result_type == ResultType.INTERRUPT
    assert result.user_notice == 'Voice transcription failed.'


@pytest.mark.asyncio
async def test_tts_disabled_continues(mock_app, sample_query):
    sample_query.pipeline_config = {
        'speech': {
            'text-to-speech': {
                'enable': False,
                'model': 'tts-model-uuid',
            }
        }
    }
    sample_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='Hello')])]
    stage = speech_module.TextToSpeechStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'TextToSpeechStage')
    assert result.result_type == ResultType.CONTINUE


@pytest.mark.asyncio
async def test_tts_voice_input_only_skips_when_not_voice(mock_app, sample_query):
    sample_query.variables['_input_was_voice'] = False
    sample_query.pipeline_config = {
        'speech': {
            'text-to-speech': {
                'enable': True,
                'model': 'tts-model-uuid',
                'trigger': 'voice-input-only',
            }
        }
    }
    sample_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='Hello')])]
    stage = speech_module.TextToSpeechStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'TextToSpeechStage')
    assert result.result_type == ResultType.CONTINUE
    assert len(sample_query.resp_message_chain[-1]) == 1
    assert isinstance(sample_query.resp_message_chain[-1][0], platform_message.Plain)


@pytest.mark.asyncio
async def test_tts_voice_only_success(mock_app, sample_query):
    sample_query.variables['_input_was_voice'] = True
    sample_query.pipeline_config = {
        'speech': {
            'text-to-speech': {
                'enable': True,
                'model': 'tts-model-uuid',
                'trigger': 'voice-input-only',
                'output': 'voice-only',
            }
        }
    }
    sample_query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='**Hello** [world](https://example.com)!')])
    ]

    mock_tts_model = Mock()
    mock_tts_model.execution_context = Mock()
    mock_tts_model.extra_args = {'voice': 'alloy'}
    mock_tts_model.provider = Mock()
    mock_tts_model.provider.invoke_tts = AsyncMock(return_value=Mock(content=b'fake-mp3-audio-content'))
    mock_app.model_mgr.get_tts_model_by_uuid = AsyncMock(return_value=mock_tts_model)

    stage = speech_module.TextToSpeechStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'TextToSpeechStage')

    assert result.result_type == ResultType.CONTINUE
    assert len(sample_query.resp_message_chain[-1]) == 1
    voice_comp = sample_query.resp_message_chain[-1][0]
    assert isinstance(voice_comp, platform_message.Voice)
    assert voice_comp.base64.startswith('data:audio/mp3;base64,')
    mock_tts_model.provider.invoke_tts.assert_called_once()
    assert mock_tts_model.provider.invoke_tts.call_args[1]['text'] == 'Hello world!'


@pytest.mark.asyncio
async def test_tts_voice_and_text_success(mock_app, sample_query):
    sample_query.pipeline_config = {
        'speech': {
            'text-to-speech': {
                'enable': True,
                'model': 'tts-model-uuid',
                'trigger': 'always',
                'output': 'voice-and-text',
            }
        }
    }
    sample_query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='Response with both voice and text')])
    ]

    mock_tts_model = Mock()
    mock_tts_model.execution_context = Mock()
    mock_tts_model.extra_args = {}
    mock_tts_model.provider = Mock()
    mock_tts_model.provider.invoke_tts = AsyncMock(return_value=Mock(content=b'fake-audio'))
    mock_app.model_mgr.get_tts_model_by_uuid = AsyncMock(return_value=mock_tts_model)

    stage = speech_module.TextToSpeechStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'TextToSpeechStage')

    assert result.result_type == ResultType.CONTINUE
    assert len(sample_query.resp_message_chain[-1]) == 2
    assert isinstance(sample_query.resp_message_chain[-1][0], platform_message.Plain)
    assert isinstance(sample_query.resp_message_chain[-1][1], platform_message.Voice)


@pytest.mark.asyncio
async def test_tts_max_text_length_fallback(mock_app, sample_query):
    sample_query.pipeline_config = {
        'speech': {
            'text-to-speech': {
                'enable': True,
                'model': 'tts-model-uuid',
                'trigger': 'always',
                'max-text-length': 10,
            }
        }
    }
    sample_query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='This is a long response text exceeding 10 chars')])
    ]

    mock_tts_model = Mock()
    mock_app.model_mgr.get_tts_model_by_uuid = AsyncMock(return_value=mock_tts_model)

    stage = speech_module.TextToSpeechStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    result = await stage.process(sample_query, 'TextToSpeechStage')

    assert result.result_type == ResultType.CONTINUE
    assert len(sample_query.resp_message_chain[-1]) == 1
    assert isinstance(sample_query.resp_message_chain[-1][0], platform_message.Plain)
