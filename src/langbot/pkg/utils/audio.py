from __future__ import annotations

import asyncio
import base64
import importlib.util
import os
import shutil
import subprocess
import tempfile
import typing

if typing.TYPE_CHECKING:
    import langbot_plugin.api.entities.builtin.platform.message as platform_message


class AudioDependencyError(RuntimeError):
    """Raised when an audio transcoding tool or optional dependency is missing or fails."""
    pass


def is_ffmpeg_available() -> bool:
    """Check if the ffmpeg command line tool is installed and available in PATH."""
    return shutil.which('ffmpeg') is not None


def is_silk_available() -> bool:
    """Check if the pilk library is installed."""
    return importlib.util.find_spec('pilk') is not None


def detect_audio_format(data: bytes) -> str:
    """Detect audio format from magic bytes."""
    if not data or len(data) < 4:
        return 'unknown'

    if data.startswith(b'#!AMR'):
        return 'amr'

    if data.startswith(b'\x02#!SILK_V3') or data.startswith(b'#!SILK_V3'):
        return 'silk'

    if data.startswith(b'RIFF') and len(data) >= 12 and data[8:12] == b'WAVE':
        return 'wav'

    if data.startswith(b'OggS'):
        if b'OpusHead' in data[:100]:
            return 'opus'
        return 'ogg'

    if data.startswith(b'ID3'):
        return 'mp3'

    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return 'mp3'

    if data.startswith(b'fLaC'):
        return 'flac'

    if len(data) >= 8 and data[4:8] == b'ftyp':
        return 'm4a'

    return 'unknown'


def transcode_audio_sync(
    audio_bytes: bytes,
    target_format: str,
    source_format: str | None = None,
) -> bytes:
    """Synchronously transcode audio bytes to target_format."""
    target_format = target_format.lower().lstrip('.')
    if target_format == 'opus':
        target_format = 'ogg'

    if not source_format or source_format == 'unknown':
        source_format = detect_audio_format(audio_bytes)

    if source_format == 'opus':
        source_format = 'ogg'

    if source_format == target_format and source_format != 'unknown':
        return audio_bytes

    # Handle SILK decoding
    if source_format == 'silk':
        if not is_silk_available():
            raise AudioDependencyError(
                "Transcoding SILK audio requires 'pilk'. Install it via 'pip install pilk' or 'pip install langbot[audio]'."
            )
        if not is_ffmpeg_available():
            raise AudioDependencyError("Transcoding requires 'ffmpeg' which is not installed on the system.")

        import pilk

        with tempfile.TemporaryDirectory() as tmpdir:
            silk_path = os.path.join(tmpdir, 'input.silk')
            pcm_path = os.path.join(tmpdir, 'decoded.pcm')
            with open(silk_path, 'wb') as f:
                f.write(audio_bytes)

            try:
                pilk.decode(silk_path, pcm_path)
            except Exception as exc:
                raise AudioDependencyError(f'Failed to decode SILK audio: {exc}') from exc

            # Convert PCM to target format via ffmpeg
            cmd = ['ffmpeg', '-y', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', pcm_path]
            if target_format == 'mp3':
                cmd.extend(['-f', 'mp3'])
            elif target_format == 'ogg':
                cmd.extend(['-c:a', 'libopus', '-f', 'ogg'])
            elif target_format == 'wav':
                cmd.extend(['-f', 'wav'])
            elif target_format == 'amr':
                cmd.extend(['-ar', '8000', '-ac', '1', '-c:a', 'libopencore_amrnb', '-f', 'amr'])
            else:
                cmd.extend(['-f', target_format])
            cmd.append('pipe:1')

            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode != 0:
                raise AudioDependencyError(
                    f"ffmpeg conversion failed from silk(pcm) to {target_format}: {proc.stderr.decode('utf-8', errors='replace')}"
                )
            return proc.stdout

    # Handle SILK encoding
    if target_format == 'silk':
        if not is_silk_available():
            raise AudioDependencyError(
                "Transcoding to SILK requires 'pilk'. Install it via 'pip install pilk' or 'pip install langbot[audio]'."
            )
        if not is_ffmpeg_available():
            raise AudioDependencyError("Transcoding requires 'ffmpeg' which is not installed on the system.")

        import pilk

        # Convert source audio to PCM s16le, 24000Hz, mono
        cmd = ['ffmpeg', '-y']
        if source_format and source_format != 'unknown':
            cmd.extend(['-f', source_format])
        cmd.extend(['-i', 'pipe:0', '-f', 's16le', '-ar', '24000', '-ac', '1', 'pipe:1'])

        proc = subprocess.run(cmd, input=audio_bytes, capture_output=True)
        if proc.returncode != 0:
            raise AudioDependencyError(
                f"ffmpeg conversion failed from {source_format} to pcm: {proc.stderr.decode('utf-8', errors='replace')}"
            )
        pcm_bytes = proc.stdout

        with tempfile.TemporaryDirectory() as tmpdir:
            pcm_path = os.path.join(tmpdir, 'input.pcm')
            silk_path = os.path.join(tmpdir, 'output.silk')
            with open(pcm_path, 'wb') as f:
                f.write(pcm_bytes)

            try:
                pilk.encode(pcm_path, silk_path, pcm_rate=24000, tencent=True)
            except Exception as exc:
                raise AudioDependencyError(f'Failed to encode SILK audio: {exc}') from exc

            with open(silk_path, 'rb') as f:
                return f.read()

    # Standard ffmpeg transcoding
    if not is_ffmpeg_available():
        raise AudioDependencyError("Transcoding requires 'ffmpeg' which is not installed on the system.")

    cmd = ['ffmpeg', '-y']
    if source_format and source_format != 'unknown':
        cmd.extend(['-f', source_format])
    cmd.extend(['-i', 'pipe:0'])

    if target_format == 'mp3':
        cmd.extend(['-f', 'mp3'])
    elif target_format == 'ogg':
        cmd.extend(['-c:a', 'libopus', '-f', 'ogg'])
    elif target_format == 'wav':
        cmd.extend(['-f', 'wav'])
    elif target_format == 'amr':
        cmd.extend(['-ar', '8000', '-ac', '1', '-c:a', 'libopencore_amrnb', '-f', 'amr'])
    else:
        cmd.extend(['-f', target_format])
    cmd.append('pipe:1')

    proc = subprocess.run(cmd, input=audio_bytes, capture_output=True)
    if proc.returncode != 0:
        raise AudioDependencyError(
            f"ffmpeg conversion failed from {source_format} to {target_format}: {proc.stderr.decode('utf-8', errors='replace')}"
        )
    return proc.stdout


async def transcode_audio(
    audio_bytes: bytes,
    target_format: str,
    source_format: str | None = None,
) -> bytes:
    """Asynchronously transcode audio bytes to target_format."""
    return await asyncio.to_thread(transcode_audio_sync, audio_bytes, target_format, source_format)


async def extract_voice_bytes(voice: platform_message.Voice) -> tuple[bytes, str]:
    """Extract raw bytes and audio format from a platform_message.Voice component."""
    if voice.base64:
        b64_str = voice.base64
        format_hint = 'unknown'
        if b64_str.startswith('data:'):
            header, _, b64_str = b64_str.partition(',')
            if ';' in header:
                mime_part = header[5:].split(';')[0]
                if '/' in mime_part:
                    format_hint = mime_part.split('/')[-1]
        raw_bytes = await asyncio.to_thread(base64.b64decode, b64_str)
        detected = detect_audio_format(raw_bytes)
        return raw_bytes, detected if detected != 'unknown' else format_hint

    if voice.path:
        with open(voice.path, 'rb') as f:
            raw_bytes = await asyncio.to_thread(f.read)
        detected = detect_audio_format(raw_bytes)
        return raw_bytes, detected

    if voice.url:
        from ...http import client as httpclient

        session = httpclient.get_session()
        async with session.get(voice.url) as response:
            raw_bytes = await response.read()
        detected = detect_audio_format(raw_bytes)
        return raw_bytes, detected

    raise ValueError('Voice component contains no base64, path, or url')
