from __future__ import annotations

import io
import unittest
from unittest.mock import patch
import wave

import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.pkg.utils import audio as audio_utils


def _create_sample_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\x00' * 3200)
    return buf.getvalue()


class TestAudioUtils(unittest.IsolatedAsyncioTestCase):
    def test_detect_audio_format(self):
        sample_wav = _create_sample_wav()
        self.assertEqual(audio_utils.detect_audio_format(sample_wav), 'wav')
        self.assertEqual(audio_utils.detect_audio_format(b'#!AMR\n12345'), 'amr')
        self.assertEqual(audio_utils.detect_audio_format(b'#!SILK_V3\n'), 'silk')
        self.assertEqual(audio_utils.detect_audio_format(b'\x02#!SILK_V3\n'), 'silk')
        self.assertEqual(audio_utils.detect_audio_format(b'OggS\x00\x02...OpusHead...'), 'opus')
        self.assertEqual(audio_utils.detect_audio_format(b'OggS\x00\x02...'), 'ogg')
        self.assertEqual(audio_utils.detect_audio_format(b'ID3\x03\x00\x00'), 'mp3')
        self.assertEqual(audio_utils.detect_audio_format(b'\xff\xfb\x90\x64'), 'mp3')
        self.assertEqual(audio_utils.detect_audio_format(b'fLaC\x00\x00'), 'flac')
        self.assertEqual(audio_utils.detect_audio_format(b''), 'unknown')
        self.assertEqual(audio_utils.detect_audio_format(b'12'), 'unknown')

    def test_is_ffmpeg_and_silk_available(self):
        with patch.object(audio_utils.shutil, 'which', return_value='/usr/bin/ffmpeg'):
            self.assertTrue(audio_utils.is_ffmpeg_available())
        with (
            patch.object(audio_utils.shutil, 'which', return_value=None),
            patch.object(audio_utils.os.path, 'isfile', return_value=False),
            patch.dict('sys.modules', {'imageio_ffmpeg': None}),
        ):
            self.assertFalse(audio_utils.is_ffmpeg_available())
        with patch.object(audio_utils.importlib.util, 'find_spec', return_value=object()):
            self.assertTrue(audio_utils.is_silk_available())
        with patch.object(audio_utils.importlib.util, 'find_spec', return_value=None):
            self.assertFalse(audio_utils.is_silk_available())

    @unittest.skipUnless(audio_utils.is_ffmpeg_available(), 'ffmpeg is not installed')
    async def test_transcode_audio_wav_to_mp3_and_ogg(self):
        sample_wav = _create_sample_wav()
        mp3_bytes = await audio_utils.transcode_audio(sample_wav, 'mp3', 'wav')
        self.assertTrue(len(mp3_bytes) > 0)
        self.assertEqual(audio_utils.detect_audio_format(mp3_bytes), 'mp3')

        ogg_bytes = await audio_utils.transcode_audio(sample_wav, 'ogg', 'wav')
        self.assertTrue(len(ogg_bytes) > 0)
        fmt = audio_utils.detect_audio_format(ogg_bytes)
        self.assertIn(fmt, ('ogg', 'opus'))

    async def test_transcode_same_format_returns_input(self):
        sample_wav = _create_sample_wav()
        result = await audio_utils.transcode_audio(sample_wav, 'wav', 'wav')
        self.assertEqual(result, sample_wav)

    def test_transcode_missing_ffmpeg_raises_error(self):
        sample_wav = _create_sample_wav()
        with patch.object(audio_utils, 'is_ffmpeg_available', return_value=False):
            with self.assertRaises(audio_utils.AudioDependencyError):
                audio_utils.transcode_audio_sync(sample_wav, 'mp3', 'wav')

    def test_transcode_missing_silk_raises_error(self):
        sample_wav = _create_sample_wav()
        with patch.object(audio_utils, 'is_silk_available', return_value=False):
            with self.assertRaises(audio_utils.AudioDependencyError):
                audio_utils.transcode_audio_sync(sample_wav, 'silk', 'wav')

    async def test_extract_voice_bytes_from_base64(self):
        import base64

        sample_wav = _create_sample_wav()
        b64_raw = base64.b64encode(sample_wav).decode('ascii')
        voice_raw = platform_message.Voice(base64=b64_raw)
        data, fmt = await audio_utils.extract_voice_bytes(voice_raw)
        self.assertEqual(data, sample_wav)
        self.assertEqual(fmt, 'wav')

        data_uri = f'data:audio/wav;base64,{b64_raw}'
        voice_uri = platform_message.Voice(base64=data_uri)
        data2, fmt2 = await audio_utils.extract_voice_bytes(voice_uri)
        self.assertEqual(data2, sample_wav)
        self.assertEqual(fmt2, 'wav')
