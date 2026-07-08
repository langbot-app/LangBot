"""Async HTTP client for the OpenClaw WeChat API.

Implements the iLink Bot API protocol.
Reference: https://github.com/epiral/weixin-bot

Endpoints: getUpdates (long-poll), sendMessage, getUploadUrl, getConfig, sendTyping.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import struct
import typing
import uuid
from typing import Optional
from urllib.parse import quote

import aiohttp

from .types import (
    ApiError,
    CDNMedia,
    FileItem,
    GetConfigResponse,
    GetUpdatesResponse,
    GetUploadUrlResponse,
    ImageItem,
    LoginResult,
    MessageItem,
    QRCodeResponse,
    QRStatusResponse,
    RefMessage,
    TextItem,
    VideoItem,
    VoiceItem,
    WeixinMessage,
)

logger = logging.getLogger('openclaw-weixin-sdk')

DEFAULT_BASE_URL = 'https://ilinkai.weixin.qq.com'
CDN_BASE_URL = 'https://novac2c.cdn.weixin.qq.com/c2c'

CHANNEL_VERSION = '1.0.0'

DEFAULT_API_TIMEOUT = 15
DEFAULT_LONG_POLL_TIMEOUT = 40
DEFAULT_CONFIG_TIMEOUT = 10
DEFAULT_QR_POLL_TIMEOUT = 35

SESSION_EXPIRED_ERRCODE = -14

DEFAULT_BOT_TYPE = '3'

# Maximum text length per message chunk (WeChat limit)
MAX_TEXT_CHUNK_SIZE = 2000


def _random_wechat_uin() -> str:
    """Generate the X-WECHAT-UIN header: random uint32 -> decimal string -> base64."""
    rand_bytes = os.urandom(4)
    uint32_val = struct.unpack('>I', rand_bytes)[0]
    return base64.b64encode(str(uint32_val).encode('utf-8')).decode('utf-8')


def _build_base_info() -> dict:
    """Build the base_info payload included in every API request."""
    return {'channel_version': CHANNEL_VERSION}


def _chunk_text(text: str, max_size: int = MAX_TEXT_CHUNK_SIZE) -> list[str]:
    """Split long text into chunks that fit within WeChat's message size limit."""
    if len(text) <= max_size:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:max_size])
        text = text[max_size:]
    return chunks


class OpenClawWeixinClient:
    """Async client for the OpenClaw WeChat HTTP JSON API."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_headers(self) -> dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'AuthorizationType': 'ilink_bot_token',
            'X-WECHAT-UIN': _random_wechat_uin(),
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    async def _post(self, endpoint: str, payload: dict, timeout: float = DEFAULT_API_TIMEOUT) -> dict:
        """Make a POST request and return the JSON response.

        Raises ApiError on HTTP errors or when the response contains a non-zero errcode.
        """
        payload['base_info'] = _build_base_info()

        session = await self._get_session()
        url = f'{self.base_url}/{endpoint}'
        headers = self._build_headers()

        async with session.post(
            url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ApiError(
                    f'OpenClaw API error {resp.status}: {text}',
                    status=resp.status,
                )
            data = await resp.json(content_type=None)

        # Check for application-level errors in the response body
        errcode = data.get('errcode') or data.get('ret')
        if errcode and errcode != 0:
            raise ApiError(
                data.get('errmsg') or f'API errcode {errcode}',
                status=200,
                code=errcode,
                payload=data,
            )

        return data

    async def get_updates(
        self, get_updates_buf: str = '', timeout: float = DEFAULT_LONG_POLL_TIMEOUT
    ) -> GetUpdatesResponse:
        """Long-poll for new messages.

        Note: This method does NOT raise ApiError for errcode responses —
        it returns them in the GetUpdatesResponse so the caller can handle
        session expiry and other errors with full context.
        """
        try:
            # Bypass the errcode check in _post since get_updates needs
            # to return error info (e.g. session expired) to the caller.
            payload: dict = {'get_updates_buf': get_updates_buf}
            payload['base_info'] = _build_base_info()

            session = await self._get_session()
            url = f'{self.base_url}/ilink/bot/getupdates'
            headers = self._build_headers()

            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ApiError(
                        f'OpenClaw API error {resp.status}: {text}',
                        status=resp.status,
                    )
                data = await resp.json(content_type=None)

        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
            return GetUpdatesResponse(ret=0, msgs=[], get_updates_buf=get_updates_buf)
        except ApiError:
            raise
        except Exception as e:
            if 'timeout' in str(e).lower():
                return GetUpdatesResponse(ret=0, msgs=[], get_updates_buf=get_updates_buf)
            raise

        return _parse_get_updates_response(data)

    async def send_message(
        self,
        to_user_id: str,
        item_list: list[MessageItem],
        context_token: str = '',
    ) -> None:
        """Send a message to a user."""
        items_payload = [_message_item_to_dict(item) for item in item_list]

        payload = {
            'msg': {
                'from_user_id': '',
                'to_user_id': to_user_id,
                'client_id': f'langbot-{uuid.uuid4().hex[:16]}',
                'message_type': WeixinMessage.TYPE_BOT,
                'message_state': WeixinMessage.STATE_FINISH,
                'item_list': items_payload,
                'context_token': context_token or None,
            }
        }
        await self._post('ilink/bot/sendmessage', payload)

    async def send_text(self, to_user_id: str, text: str, context_token: str = '') -> None:
        """Send a plain text message, automatically chunking if too long."""
        chunks = _chunk_text(text)
        for chunk in chunks:
            item = MessageItem(type=MessageItem.TEXT, text_item=TextItem(text=chunk))
            await self.send_message(to_user_id, [item], context_token)

    async def get_config(self, ilink_user_id: str, context_token: str = '') -> GetConfigResponse:
        """Get bot config including typing_ticket."""
        data = await self._post(
            'ilink/bot/getconfig',
            {'ilink_user_id': ilink_user_id, 'context_token': context_token or None},
            timeout=DEFAULT_CONFIG_TIMEOUT,
        )
        return GetConfigResponse(
            ret=data.get('ret'),
            errmsg=data.get('errmsg'),
            typing_ticket=data.get('typing_ticket'),
        )

    async def send_typing(self, ilink_user_id: str, typing_ticket: str, status: int = 1) -> None:
        """Send typing indicator. status: 1=typing, 2=cancel."""
        await self._post(
            'ilink/bot/sendtyping',
            {
                'ilink_user_id': ilink_user_id,
                'typing_ticket': typing_ticket,
                'status': status,
            },
            timeout=DEFAULT_CONFIG_TIMEOUT,
        )

    async def stop_typing(self, ilink_user_id: str, typing_ticket: str) -> None:
        """Cancel the typing indicator for a user."""
        await self.send_typing(ilink_user_id, typing_ticket, status=2)

    async def download_media(
        self,
        media: CDNMedia,
    ) -> bytes:
        """Download and decrypt a file from the WeChat CDN.

        Args:
            media: CDNMedia object with encrypt_query_param and aes_key.

        Returns:
            Decrypted file bytes.
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7

        if not media.encrypt_query_param:
            raise ApiError('CDN media has no encrypt_query_param', status=0)
        if not media.aes_key:
            raise ApiError('CDN media has no aes_key', status=0)

        # Derive 16-byte AES key
        # aes_key is base64-encoded; the decoded content may be:
        #   - raw 16 bytes (direct AES key)
        #   - 32-char hex string (decode hex to get 16 bytes)
        raw = base64.b64decode(media.aes_key)
        if len(raw) == 16:
            aes_key = raw
        elif len(raw) == 32:
            # Hex-encoded 16-byte key
            aes_key = bytes.fromhex(raw.decode('utf-8'))
        else:
            raise ApiError(f'Invalid AES key length: {len(raw)} (expected 16 or 32)', status=0)

        # Download encrypted bytes from CDN
        session = await self._get_session()
        cdn_url = f'{CDN_BASE_URL}/download?encrypted_query_param={quote(media.encrypt_query_param, safe="")}'

        async with session.get(cdn_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ApiError(f'CDN download failed: {resp.status} {text}', status=resp.status)
            encrypted = await resp.read()

        # Decrypt AES-128-ECB with PKCS7 padding
        cipher = Cipher(algorithms.AES(aes_key), modes.ECB())
        decryptor = cipher.decryptor()
        padded = decryptor.update(encrypted) + decryptor.finalize()

        unpadder = PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()

    async def upload_media(
        self,
        file_bytes: bytes,
        to_user_id: str,
        media_type: int,
    ) -> CDNMedia:
        """Encrypt and upload media to WeChat CDN.

        Args:
            file_bytes: Raw file bytes to upload.
            to_user_id: Recipient user ID.
            media_type: 1=IMAGE, 2=VIDEO, 3=FILE, 4=VOICE.

        Returns:
            CDNMedia with encrypt_query_param and aes_key for use in sendMessage.
        """
        import hashlib

        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7

        # 1. Generate random 16-byte AES key
        raw_key = os.urandom(16)
        aes_key_hex = raw_key.hex()  # 32-char hex string

        # 2. Encode key for CDNMedia: base64(hex_string) — same for all media types
        # Matches official SDK: Buffer.from(aeskey_hex).toString("base64")
        encoded_key = base64.b64encode(aes_key_hex.encode('utf-8')).decode('utf-8')

        # 3. Encrypt file with AES-128-ECB + PKCS7
        padder = PKCS7(128).padder()
        padded = padder.update(file_bytes) + padder.finalize()
        cipher = Cipher(algorithms.AES(raw_key), modes.ECB())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()

        # 4. Get upload URL
        raw_md5 = hashlib.md5(file_bytes).hexdigest()
        filekey = os.urandom(16).hex()  # 32-char hex, matches official SDK

        upload_resp = await self.get_upload_url(
            filekey=filekey,
            media_type=media_type,
            to_user_id=to_user_id,
            rawsize=len(file_bytes),
            rawfilemd5=raw_md5,
            filesize=len(encrypted),
            aeskey=aes_key_hex,  # hex string, as expected by the API
        )

        if not upload_resp.upload_param:
            raise ApiError('Failed to get upload URL', status=0)

        # 5. Upload to CDN
        # upload_param is an opaque token from the server — pass it as-is
        session = await self._get_session()
        cdn_url = f'{CDN_BASE_URL}/upload?encrypted_query_param={quote(upload_resp.upload_param, safe="")}&filekey={quote(filekey, safe="")}'
        logger.debug(
            'CDN upload: url=%s raw_size=%d encrypted_size=%d md5=%s aeskey=%s',
            cdn_url,
            len(file_bytes),
            len(encrypted),
            raw_md5,
            encoded_key,
        )

        async with session.post(
            cdn_url,
            data=encrypted,
            headers={'Content-Type': 'application/octet-stream'},
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error('CDN upload failed: status=%d url=%s body=%s', resp.status, cdn_url, text[:500])
                raise ApiError(f'CDN upload failed: {resp.status} {text}', status=resp.status)
            download_param = resp.headers.get('x-encrypted-param', '')

        if not download_param:
            raise ApiError('CDN upload succeeded but no x-encrypted-param returned', status=0)

        return CDNMedia(
            encrypt_query_param=download_param,
            aes_key=encoded_key,
            encrypt_type=1,
        )

    async def send_image(
        self,
        to_user_id: str,
        image_bytes: bytes,
        context_token: str = '',
    ) -> None:
        """Upload an image to CDN and send it."""
        media = await self.upload_media(image_bytes, to_user_id, media_type=1)
        item = MessageItem(
            type=MessageItem.IMAGE,
            image_item=ImageItem(
                media=media,
                aeskey=media.aes_key,
            ),
        )
        await self.send_message(to_user_id, [item], context_token)

    async def send_file(
        self,
        to_user_id: str,
        file_bytes: bytes,
        file_name: str,
        context_token: str = '',
    ) -> None:
        """Upload a file to CDN and send it."""
        import hashlib

        media = await self.upload_media(file_bytes, to_user_id, media_type=3)
        item = MessageItem(
            type=MessageItem.FILE,
            file_item=FileItem(
                media=media,
                file_name=file_name,
                md5=hashlib.md5(file_bytes).hexdigest(),
                len=str(len(file_bytes)),
            ),
        )
        await self.send_message(to_user_id, [item], context_token)

    async def send_voice(
        self,
        to_user_id: str,
        voice_bytes: bytes,
        playtime: int = 0,
        context_token: str = '',
    ) -> None:
        """Upload a voice message to CDN and send it."""
        media = await self.upload_media(voice_bytes, to_user_id, media_type=4)
        item = MessageItem(
            type=MessageItem.VOICE,
            voice_item=VoiceItem(
                media=media,
                playtime=playtime,
            ),
        )
        await self.send_message(to_user_id, [item], context_token)

    async def get_upload_url(
        self,
        filekey: str,
        media_type: int,
        to_user_id: str,
        rawsize: int,
        rawfilemd5: str,
        filesize: int,
        thumb_rawsize: Optional[int] = None,
        thumb_rawfilemd5: Optional[str] = None,
        thumb_filesize: Optional[int] = None,
        aeskey: Optional[str] = None,
    ) -> GetUploadUrlResponse:
        """Get a pre-signed CDN upload URL."""
        payload: dict = {
            'filekey': filekey,
            'media_type': media_type,
            'to_user_id': to_user_id,
            'rawsize': rawsize,
            'rawfilemd5': rawfilemd5,
            'filesize': filesize,
            'no_need_thumb': True,
        }
        if thumb_rawsize is not None:
            payload['thumb_rawsize'] = thumb_rawsize
        if thumb_rawfilemd5 is not None:
            payload['thumb_rawfilemd5'] = thumb_rawfilemd5
        if thumb_filesize is not None:
            payload['thumb_filesize'] = thumb_filesize
        if aeskey is not None:
            payload['aeskey'] = aeskey

        data = await self._post('ilink/bot/getuploadurl', payload)
        logger.debug('get_upload_url response: %s', data)
        return GetUploadUrlResponse(
            upload_param=data.get('upload_param'),
            thumb_upload_param=data.get('thumb_upload_param'),
        )

    # -----------------------------------------------------------------------
    # QR Code Login
    # -----------------------------------------------------------------------

    async def fetch_qrcode(self, bot_type: str = DEFAULT_BOT_TYPE) -> QRCodeResponse:
        """Fetch a QR code for WeChat login authorization (GET, no auth needed)."""
        session = await self._get_session()
        url = f'{self.base_url}/ilink/bot/get_bot_qrcode?bot_type={bot_type}'

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=DEFAULT_API_TIMEOUT)) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ApiError(
                    f'Failed to fetch QR code: {resp.status} {text}',
                    status=resp.status,
                )
            data = await resp.json(content_type=None)

        logger.debug(
            'fetch_qrcode response: qrcode=%s, img=%s', data.get('qrcode'), bool(data.get('qrcode_img_content'))
        )

        return QRCodeResponse(
            qrcode=data.get('qrcode'),
            qrcode_img_content=data.get('qrcode_img_content'),
        )

    async def _fetch_qr_image_base64(self, url: str) -> str:
        """Generate a QR code image from the URL and return a data URI string.

        The qrcode_img_content URL points to an HTML page (not a raw image),
        so we generate the QR code locally using the qrcode library.
        """
        import qrcode

        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{b64}'

    async def poll_qrcode_status(self, qrcode: str) -> QRStatusResponse:
        """Long-poll the QR code scan status (GET with iLink-App-ClientVersion header)."""
        session = await self._get_session()
        url = f'{self.base_url}/ilink/bot/get_qrcode_status?qrcode={quote(qrcode, safe="")}'
        headers = {'iLink-App-ClientVersion': '1'}

        try:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=DEFAULT_QR_POLL_TIMEOUT)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ApiError(
                        f'Failed to poll QR status: {resp.status} {text}',
                        status=resp.status,
                    )
                data = await resp.json(content_type=None)
                logger.debug('QR status poll response: %s', data)
        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
            return QRStatusResponse(status='wait')

        return QRStatusResponse(
            status=data.get('status'),
            bot_token=data.get('bot_token'),
            ilink_bot_id=data.get('ilink_bot_id'),
            baseurl=data.get('baseurl'),
            ilink_user_id=data.get('ilink_user_id'),
        )

    async def login(
        self,
        max_retries: int = 5,
        poll_timeout_ms: int = 480_000,
        on_qrcode: Optional[typing.Callable[[str, str], typing.Any]] = None,
        on_status: Optional[typing.Callable[[str], typing.Any]] = None,
    ) -> LoginResult:
        """Complete QR code login flow with auto-retry on expiry.

        Args:
            max_retries: Max number of QR code refreshes on expiry.
            poll_timeout_ms: Timeout per QR code in milliseconds.
            on_qrcode: Callback(qr_image_base64, qr_url) called each time a
                        new QR code is fetched. Use this to display the QR code.
            on_status: Callback(status_str) called on each status poll change.

        Returns:
            LoginResult with token, base_url, and account_id.

        Raises:
            ApiError: On unrecoverable API errors.
            Exception: If all retries are exhausted.
        """
        last_qr_base64: Optional[str] = None

        for attempt in range(max_retries):
            qr_resp = await self.fetch_qrcode()
            if not qr_resp.qrcode or not qr_resp.qrcode_img_content:
                raise ApiError('Failed to get QR code from server', status=0)

            # Convert QR image to base64 and notify caller
            last_qr_base64 = await self._fetch_qr_image_base64(qr_resp.qrcode_img_content)
            if on_qrcode:
                try:
                    result = on_qrcode(last_qr_base64, qr_resp.qrcode_img_content)
                    if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                        await result
                except Exception as e:
                    logger.warning('on_qrcode callback error: %s', e)

            # Poll until confirmed / expired / timeout
            loop = asyncio.get_running_loop()
            deadline = loop.time() + poll_timeout_ms / 1000.0

            while loop.time() < deadline:
                try:
                    status_resp = await self.poll_qrcode_status(qr_resp.qrcode)
                except Exception as e:
                    logger.error('Error polling QR status: %s', e)
                    await asyncio.sleep(2)
                    continue

                if on_status:
                    try:
                        cb_result = on_status(status_resp.status or 'unknown')
                        if asyncio.iscoroutine(cb_result) or asyncio.isfuture(cb_result):
                            await cb_result
                    except Exception as e:
                        logger.warning('on_status callback error: %s', e)

                if status_resp.status == 'confirmed' and status_resp.bot_token:
                    new_base_url = status_resp.baseurl or self.base_url
                    # Update this client instance as well
                    self.token = status_resp.bot_token
                    self.base_url = new_base_url.rstrip('/')
                    return LoginResult(
                        token=status_resp.bot_token,
                        base_url=new_base_url,
                        account_id=status_resp.ilink_bot_id or '',
                        qr_image_base64=last_qr_base64,
                    )

                if status_resp.status == 'expired':
                    break  # retry with a new QR code

                await asyncio.sleep(1)
            else:
                # While-loop ended without break → poll timeout, treat as expired
                pass

            remaining = max_retries - attempt - 1
            if remaining > 0:
                logger.info('QR code expired, refreshing... (%d retries left)', remaining)
            else:
                raise ApiError('QR code login failed: max retries exceeded', status=0)

        # Should not reach here, but just in case
        raise ApiError('QR code login failed', status=0)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_cdn_media(data: Optional[dict]) -> Optional[CDNMedia]:
    if not data:
        return None
    return CDNMedia(
        encrypt_query_param=data.get('encrypt_query_param'),
        aes_key=data.get('aes_key'),
        encrypt_type=data.get('encrypt_type'),
    )


def _parse_message_item(data: dict) -> MessageItem:
    item = MessageItem(
        type=data.get('type'),
        create_time_ms=data.get('create_time_ms'),
        update_time_ms=data.get('update_time_ms'),
        is_completed=data.get('is_completed'),
        msg_id=data.get('msg_id'),
    )

    if data.get('text_item'):
        item.text_item = TextItem(text=data['text_item'].get('text'))

    if data.get('image_item'):
        img = data['image_item']
        item.image_item = ImageItem(
            media=_parse_cdn_media(img.get('media')),
            thumb_media=_parse_cdn_media(img.get('thumb_media')),
            aeskey=img.get('aeskey'),
            url=img.get('url'),
            mid_size=img.get('mid_size'),
        )

    if data.get('voice_item'):
        v = data['voice_item']
        item.voice_item = VoiceItem(
            media=_parse_cdn_media(v.get('media')),
            encode_type=v.get('encode_type'),
            playtime=v.get('playtime'),
            text=v.get('text'),
        )

    if data.get('file_item'):
        f = data['file_item']
        item.file_item = FileItem(
            media=_parse_cdn_media(f.get('media')),
            file_name=f.get('file_name'),
            md5=f.get('md5'),
            len=f.get('len'),
        )

    if data.get('video_item'):
        vid = data['video_item']
        item.video_item = VideoItem(
            media=_parse_cdn_media(vid.get('media')),
            video_size=vid.get('video_size'),
            play_length=vid.get('play_length'),
            video_md5=vid.get('video_md5'),
            thumb_media=_parse_cdn_media(vid.get('thumb_media')),
        )

    if data.get('ref_msg'):
        ref = data['ref_msg']
        item.ref_msg = RefMessage(
            title=ref.get('title'),
            message_item=_parse_message_item(ref['message_item']) if ref.get('message_item') else None,
        )

    return item


def _parse_weixin_message(data: dict) -> WeixinMessage:
    msg = WeixinMessage(
        seq=data.get('seq'),
        message_id=data.get('message_id'),
        from_user_id=data.get('from_user_id'),
        to_user_id=data.get('to_user_id'),
        client_id=data.get('client_id'),
        create_time_ms=data.get('create_time_ms'),
        session_id=data.get('session_id'),
        group_id=data.get('group_id'),
        message_type=data.get('message_type'),
        message_state=data.get('message_state'),
        context_token=data.get('context_token'),
    )
    if data.get('item_list'):
        msg.item_list = [_parse_message_item(item) for item in data['item_list']]
    return msg


def _parse_get_updates_response(data: dict) -> GetUpdatesResponse:
    resp = GetUpdatesResponse(
        ret=data.get('ret'),
        errcode=data.get('errcode'),
        errmsg=data.get('errmsg'),
        get_updates_buf=data.get('get_updates_buf'),
        longpolling_timeout_ms=data.get('longpolling_timeout_ms'),
    )
    if data.get('msgs'):
        resp.msgs = [_parse_weixin_message(m) for m in data['msgs']]
    return resp


def _cdn_media_to_dict(media: Optional[CDNMedia]) -> Optional[dict]:
    if not media:
        return None
    d: dict = {}
    if media.encrypt_query_param is not None:
        d['encrypt_query_param'] = media.encrypt_query_param
    if media.aes_key is not None:
        d['aes_key'] = media.aes_key
    if media.encrypt_type is not None:
        d['encrypt_type'] = media.encrypt_type
    return d or None


def _message_item_to_dict(item: MessageItem) -> dict:
    d: dict = {'type': item.type}

    if item.text_item:
        d['text_item'] = {'text': item.text_item.text}

    if item.image_item:
        img_d: dict = {}
        if item.image_item.media:
            img_d['media'] = _cdn_media_to_dict(item.image_item.media)
        if item.image_item.mid_size is not None:
            img_d['mid_size'] = item.image_item.mid_size
        d['image_item'] = img_d

    if item.voice_item:
        voice_d: dict = {}
        if item.voice_item.media:
            voice_d['media'] = _cdn_media_to_dict(item.voice_item.media)
        if item.voice_item.playtime is not None:
            voice_d['playtime'] = item.voice_item.playtime
        d['voice_item'] = voice_d

    if item.file_item:
        file_d: dict = {}
        if item.file_item.media:
            file_d['media'] = _cdn_media_to_dict(item.file_item.media)
        if item.file_item.file_name:
            file_d['file_name'] = item.file_item.file_name
        if item.file_item.len:
            file_d['len'] = item.file_item.len
        d['file_item'] = file_d

    if item.video_item:
        vid_d: dict = {}
        if item.video_item.media:
            vid_d['media'] = _cdn_media_to_dict(item.video_item.media)
        if item.video_item.video_size is not None:
            vid_d['video_size'] = item.video_item.video_size
        d['video_item'] = vid_d

    return d
