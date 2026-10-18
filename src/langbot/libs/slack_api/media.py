"""Transfer attachment bytes rather than degrading attachments to text."""

import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import urlparse, unquote

import aiohttp

from langbot.pkg.utils import httpclient, image
from langbot_plugin.api.entities.builtin.platform import message as pm

MAX_MEDIA_BYTES = 20 * 1024 * 1024
MEDIA_TYPES = (pm.Image, pm.File, pm.Voice)


async def download_media(url: str, token: str = '') -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise ValueError('Slack media requires an HTTP(S) URL')
    # Never disclose a bot token to arbitrary media hosts or redirects.
    private = parsed.scheme == 'https' and parsed.hostname == 'files.slack.com'
    headers = {'Authorization': f'Bearer {token}'} if private and token else {}
    async with httpclient.get_session().get(
        url, headers=headers, allow_redirects=not bool(headers), timeout=aiohttp.ClientTimeout(total=30)
    ) as response:
        if response.status != 200:
            raise ValueError(f'Slack media download failed (HTTP {response.status})')
        data = await httpclient.read_limited(response, max_bytes=MAX_MEDIA_BYTES)
        return data, response.headers.get('Content-Type', 'application/octet-stream').split(';')[0]


async def attachment_bytes(component, token: str = '') -> tuple[bytes, str]:
    name = getattr(component, 'name', '')
    mime = ''
    if component.base64:
        value = component.base64
        if value.startswith('data:'):
            header, value = value.split(',', 1)
            mime = header[5:].split(';')[0]
        data = await image.decode_base64_limited(value, max_bytes=MAX_MEDIA_BYTES)
    elif component.path:
        path = Path(component.path)

        def read():
            with path.open('rb') as stream:
                return stream.read(MAX_MEDIA_BYTES + 1)

        data = await asyncio.to_thread(read)
        name = name or path.name
    elif component.url:
        data, mime = await download_media(component.url, token)
        name = name or Path(unquote(urlparse(component.url).path)).name
    else:
        raise ValueError('Slack attachment has no base64, path or URL')
    if not data or len(data) > MAX_MEDIA_BYTES:
        raise ValueError('Slack attachment is empty or exceeds the 20 MiB limit')
    if not name:
        if isinstance(component, pm.Image) and not mime:
            mime = await asyncio.to_thread(_image_mime, data)
        name = 'attachment' + (mimetypes.guess_extension(mime) or '.bin')
    return data, name.replace('\\', '/').rsplit('/', 1)[-1]


def _image_mime(data: bytes) -> str:
    import io
    from PIL import Image

    with Image.open(io.BytesIO(data)) as picture:
        return Image.MIME.get(picture.format, 'application/octet-stream')


async def send_chain(
    bot, target_type: str, target_id: str, chain: pm.MessageChain, thread_ts: str | None = None
) -> dict:
    from langbot.pkg.platform.adapters.slack.message_converter import SlackMessageConverter

    if target_type not in {'person', 'channel'}:
        raise ValueError(f'Unsupported Slack target type: {target_type}')
    responses = []
    pending = []
    channel = None

    async def flush():
        if not pending:
            return
        text = await SlackMessageConverter.yiri2target(pm.MessageChain(list(pending)))
        pending.clear()
        if text:
            if thread_ts:
                response = await bot.client.chat_postMessage(channel=target_id, text=text, thread_ts=thread_ts)
                responses.append(response.data if hasattr(response, 'data') else response)
            else:
                method = bot.send_message_to_one if target_type == 'person' else bot.send_message_to_channel
                responses.append(await method(text, target_id))

    for component in chain:
        if isinstance(component, MEDIA_TYPES):
            data, filename = await attachment_bytes(component, bot.bot_token)
            await flush()
            if channel is None:
                if target_type == 'person' and not target_id.startswith('D'):
                    opened = await bot.client.conversations_open(users=[target_id])
                    channel = opened['channel']['id']
                else:
                    channel = target_id
            response = await bot.client.files_upload_v2(
                channel=channel,
                file=data,
                filename=filename,
                title=filename,
                **({'thread_ts': thread_ts} if thread_ts else {}),
            )
            if not response.get('ok'):
                raise RuntimeError(f'Slack file upload failed: {response.get("error", "unknown_error")}')
            responses.append(response.data if hasattr(response, 'data') else response)
        elif isinstance(component, pm.Forward):
            await flush()
            for node in component.node_list:
                if node.message_chain:
                    responses.append(await send_chain(bot, target_type, target_id, node.message_chain, thread_ts))
        else:
            pending.append(component)
    await flush()
    return {'target_type': target_type, 'target_id': target_id, 'responses': responses}
