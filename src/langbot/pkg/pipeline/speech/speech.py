from __future__ import annotations

import base64
import logging
import re
import typing

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from ...i18n import pipeline_notice
from ...utils import audio as audio_utils
from .. import entities, stage
from ..pool import get_query_execution_context

logger = logging.getLogger(__name__)


def strip_markdown(text: str) -> str:
    """Strip markdown formatting from text for TTS input."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove images: ![alt](url) -> ''
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
    # Replace links: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove headers (# Heading)
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Remove bold/italic (**text**, *text*, __text__, _text_)
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    # Remove strikethrough (~~text~~)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    # Remove blockquotes
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


@stage.stage_class('SpeechRecognitionStage')
class SpeechRecognitionStage(stage.PipelineStage):
    """Speech Recognition (ASR) Stage

    Transcribes incoming voice messages into plain text and updates the message chain.
    """

    async def initialize(self, pipeline_config: dict):
        pass

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        config = query.pipeline_config.get('speech', {}).get('speech-recognition', {})
        if not config.get('enable', False):
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        model_uuid = config.get('model')
        if not model_uuid:
            self.ap.logger.debug('SpeechRecognitionStage enabled but no model configured; skipping.')
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        voice_components = [comp for comp in query.message_chain if isinstance(comp, platform_message.Voice)]
        if not voice_components:
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        query.variables['_input_was_voice'] = True
        primary_voice = voice_components[0]

        max_duration = config.get('max-duration', 60)
        if primary_voice.length and primary_voice.length > max_duration:
            self.ap.logger.info(
                f'Voice message duration ({primary_voice.length}s) exceeds max-duration ({max_duration}s).'
            )
            if config.get('on-failure', 'notify') == 'notify':
                notice = pipeline_notice(
                    query,
                    'voice-duration-exceeded-hint',
                    'Voice message exceeds maximum duration.',
                )
                return entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    user_notice=notice,
                )
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        try:
            raw_bytes, source_format = await audio_utils.extract_voice_bytes(primary_voice)
            audio_bytes = raw_bytes
            target_format = source_format if source_format in ('wav', 'mp3', 'ogg', 'm4a', 'flac') else 'wav'
            if source_format != target_format and audio_utils.is_ffmpeg_available():
                audio_bytes = await audio_utils.transcode_audio(raw_bytes, target_format, source_format)
        except Exception as exc:
            self.ap.logger.error(f'Failed to extract or transcode voice bytes: {exc}')
            if config.get('on-failure', 'notify') == 'notify':
                notice = pipeline_notice(
                    query,
                    'voice-transcribe-failed-hint',
                    'Voice transcription failed.',
                )
                return entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    user_notice=notice,
                )
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        execution_context = get_query_execution_context(query)
        asr_model = await self.ap.model_mgr.get_asr_model_by_uuid(execution_context, model_uuid)
        if asr_model is None:
            self.ap.logger.error(f'ASR model {model_uuid} not found.')
            if config.get('on-failure', 'notify') == 'notify':
                notice = pipeline_notice(
                    query,
                    'voice-transcribe-failed-hint',
                    'Voice transcription failed.',
                )
                return entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    user_notice=notice,
                )
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        try:
            transcript = await asr_model.provider.invoke_asr(
                model=asr_model,
                audio=audio_bytes,
                mime=f'audio/{target_format}',
                execution_context=asr_model.execution_context,
            )
            transcript = (transcript or '').strip()
        except Exception as exc:
            self.ap.logger.error(f'ASR model invocation failed: {exc}')
            if config.get('on-failure', 'notify') == 'notify':
                notice = pipeline_notice(
                    query,
                    'voice-transcribe-failed-hint',
                    'Voice transcription failed.',
                )
                return entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    user_notice=notice,
                )
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        query.variables['voice_transcript'] = transcript

        keep_original = config.get('keep-original-voice', False)
        new_chain = []
        for comp in query.message_chain:
            if isinstance(comp, platform_message.Voice):
                if keep_original:
                    new_chain.append(comp)
                new_chain.append(platform_message.Plain(text=transcript))
            else:
                new_chain.append(comp)
        query.message_chain = platform_message.MessageChain(new_chain)

        quote = getattr(query, 'quote', None)
        if quote and getattr(quote, 'origin', None):
            new_origin = []
            for comp in quote.origin:
                if isinstance(comp, platform_message.Voice):
                    if keep_original:
                        new_origin.append(comp)
                    new_origin.append(platform_message.Plain(text=transcript))
                else:
                    new_origin.append(comp)
            quote.origin = platform_message.MessageChain(new_origin)

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)


@stage.stage_class('TextToSpeechStage')
class TextToSpeechStage(stage.PipelineStage):
    """Text to Speech Stage

    Synthesizes outgoing response text into voice and attaches/replaces with Voice component.
    """

    async def initialize(self, pipeline_config: dict):
        pass

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        config = query.pipeline_config.get('speech', {}).get('text-to-speech', {})
        if not config.get('enable', False):
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        model_uuid = config.get('model')
        if not model_uuid:
            self.ap.logger.debug('TextToSpeechStage enabled but no model configured; skipping.')
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        trigger = config.get('trigger', 'voice-input-only')
        if trigger == 'never':
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
        if trigger == 'voice-input-only' and not query.variables.get('_input_was_voice', False):
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        # Skip command messages, tool call announcements, or streaming chunks that are not final
        if query.resp_messages:
            last_resp = query.resp_messages[-1]
            if getattr(last_resp, 'role', None) == 'command':
                return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            if getattr(last_resp, 'tool_calls', None):
                return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            if hasattr(last_resp, 'is_final') and not last_resp.is_final:
                return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        if not query.resp_message_chain:
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        plain_texts = [comp.text for comp in query.resp_message_chain[-1] if isinstance(comp, platform_message.Plain)]
        full_text = ''.join(plain_texts).strip()
        if not full_text:
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        clean_text = strip_markdown(full_text)
        if not clean_text:
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        max_text_length = config.get('max-text-length', 500)
        if len(clean_text) > max_text_length:
            self.ap.logger.info(
                f'Response text length ({len(clean_text)}) exceeds max-text-length ({max_text_length}); falling back to text.'
            )
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        execution_context = get_query_execution_context(query)
        tts_model = await self.ap.model_mgr.get_tts_model_by_uuid(execution_context, model_uuid)
        if tts_model is None:
            self.ap.logger.warning(f'TTS model {model_uuid} not found; falling back to text.')
            if config.get('on-failure', 'fallback') == 'notify':
                notice = pipeline_notice(
                    query,
                    'voice-synthesis-failed-hint',
                    'Voice synthesis failed.',
                )
                return entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query,
                    user_notice=notice,
                )
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        model_extra = getattr(tts_model, 'extra_args', None)
        if model_extra is None and hasattr(tts_model, 'model_entity') and tts_model.model_entity is not None:
            model_extra = getattr(tts_model.model_entity, 'extra_args', {})
        model_extra = model_extra or {}
        voice_param = config.get('voice') or model_extra.get('voice')
        extra_args: dict[str, typing.Any] = {'response_format': 'mp3'}
        if voice_param:
            extra_args['voice'] = voice_param

        try:
            audio_bytes, mime = await tts_model.provider.invoke_tts(
                model=tts_model,
                text=clean_text,
                extra_args=extra_args,
                execution_context=tts_model.execution_context,
            )
        except Exception as exc:
            self.ap.logger.error(f'TTS invocation failed: {exc}; falling back to text.')
            if config.get('on-failure', 'fallback') == 'notify':
                notice = pipeline_notice(
                    query,
                    'voice-synthesis-failed-hint',
                    'Voice synthesis failed.',
                )
                return entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query,
                    user_notice=notice,
                )
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        b64_audio = base64.b64encode(audio_bytes).decode('ascii')
        audio_duration = audio_utils.estimate_audio_duration(
            audio_bytes, mime.split('/')[-1] if '/' in mime else 'unknown'
        )
        voice_comp = platform_message.Voice(
            base64=f'data:{mime};base64,{b64_audio}',
            length=int(round(audio_duration)) if audio_duration > 0 else None,
        )

        output_mode = config.get('output', 'voice-only')
        if output_mode == 'voice-only':
            non_plain_components = [
                comp for comp in query.resp_message_chain[-1] if not isinstance(comp, platform_message.Plain)
            ]
            query.resp_message_chain[-1] = platform_message.MessageChain([voice_comp] + non_plain_components)
        else:
            query.resp_message_chain[-1].append(voice_comp)

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
