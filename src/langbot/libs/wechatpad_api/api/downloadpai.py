import asyncio
import base64

import httpx

from langbot.libs.wechatpad_api.util.http_util import post_json
from langbot.pkg.utils import httpclient


_MAX_WECHATPAD_MEDIA_BYTES = 16 * 1024 * 1024


async def _read_media_limited(response: httpx.Response) -> bytes:
    content_length = response.headers.get('content-length')
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = None
        if declared_size is not None and declared_size > _MAX_WECHATPAD_MEDIA_BYTES:
            raise RuntimeError('WeChatPad media exceeds the runtime limit')

    body = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
        body.extend(chunk)
        if len(body) > _MAX_WECHATPAD_MEDIA_BYTES:
            raise RuntimeError('WeChatPad media exceeds the runtime limit')
    return bytes(body)


class DownloadApi:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def send_download(self, aeskey, file_type, file_url):
        json_data = {'AesKey': aeskey, 'FileType': file_type, 'FileURL': file_url}
        url = self.base_url + '/message/SendCdnDownload'
        return post_json(url, token=self.token, data=json_data)

    def get_msg_voice(self, buf_id, length, new_msgid):
        json_data = {'Bufid': buf_id, 'Length': length, 'NewMsgId': new_msgid, 'ToUserName': ''}
        url = self.base_url + '/message/GetMsgVoice'
        return post_json(url, token=self.token, data=json_data)

    async def download_url_to_base64(self, download_url):
        async with httpx.AsyncClient(
            timeout=30,
            event_hooks=httpclient.httpx_response_limit_hooks(_MAX_WECHATPAD_MEDIA_BYTES),
        ) as client:
            async with client.stream('GET', download_url) as response:
                if response.status_code != 200:
                    raise RuntimeError('获取文件失败')
                file_bytes = await _read_media_limited(response)
        encoded = await asyncio.to_thread(base64.b64encode, file_bytes)
        return encoded.decode('utf-8')
