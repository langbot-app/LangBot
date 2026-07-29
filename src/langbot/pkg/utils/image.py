import base64
import typing
import io
from urllib.parse import urlparse, parse_qs
import ssl

import aiohttp

from langbot.pkg.utils import httpclient
import PIL.Image

import asyncio

_INSECURE_SSL_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
_INSECURE_SSL_CONTEXT.check_hostname = False
_INSECURE_SSL_CONTEXT.verify_mode = ssl.CERT_NONE
DEFAULT_BASE64_MEDIA_LIMIT = 10 * 1024 * 1024


def _detect_image_format(file_bytes: bytes) -> str:
    with PIL.Image.open(io.BytesIO(file_bytes)) as image:
        return str(image.format or 'jpeg').lower()


def _decode_base64_limited(value: str, max_bytes: int) -> bytes:
    max_bytes = max(int(max_bytes), 1)
    max_encoded_chars = 4 * ((max_bytes + 2) // 3) + 4
    if len(value) > max_encoded_chars:
        raise ValueError(f'Base64 media exceeds the {max_bytes}-byte limit')
    decoded = base64.b64decode(value)
    if len(decoded) > max_bytes:
        raise ValueError(f'Base64 media exceeds the {max_bytes}-byte limit')
    return decoded


async def decode_base64_limited(
    value: str,
    *,
    max_bytes: int = DEFAULT_BASE64_MEDIA_LIMIT,
) -> bytes:
    """Decode bounded media outside the event loop."""

    return await asyncio.to_thread(_decode_base64_limited, value, max_bytes)


async def encode_base64(data: bytes) -> str:
    """Encode a bounded byte payload outside the event loop."""

    return (await asyncio.to_thread(base64.b64encode, data)).decode('utf-8')


async def get_gewechat_image_base64(
    gewechat_url: str,
    gewechat_file_url: str,
    app_id: str,
    xml_content: str,
    token: str,
    image_type: int = 2,
) -> typing.Tuple[str, str]:
    """从gewechat服务器获取图片并转换为base64格式

    Args:
        gewechat_url (str): gewechat服务器地址（用于获取图片URL）
        gewechat_file_url (str): gewechat文件下载服务地址
        app_id (str): gewechat应用ID
        xml_content (str): 图片的XML内容
        token (str): Gewechat API Token
        image_type (int, optional): 图片类型. Defaults to 2.

    Returns:
        typing.Tuple[str, str]: (base64编码, 图片格式)

    Raises:
        aiohttp.ClientTimeout: 请求超时（15秒）或连接超时（2秒）
        Exception: 其他错误
    """
    headers = {'X-GEWE-TOKEN': token, 'Content-Type': 'application/json'}

    # 设置超时
    timeout = aiohttp.ClientTimeout(
        total=15.0,  # 总超时时间15秒
        connect=2.0,  # 连接超时2秒
        sock_connect=2.0,  # socket连接超时2秒
        sock_read=15.0,  # socket读取超时15秒
    )

    try:
        session = httpclient.get_session()
        # 获取图片下载链接
        try:
            async with session.post(
                f'{gewechat_url}/v2/api/message/downloadImage',
                headers=headers,
                json={'appId': app_id, 'type': image_type, 'xml': xml_content},
                timeout=timeout,
            ) as response:
                if response.status != 200:
                    error = await httpclient.read_text_limited(response)
                    raise Exception(f'获取gewechat图片下载失败: {error}')

                resp_data = await httpclient.read_json_limited(response)
                if resp_data.get('ret') != 200:
                    raise Exception(f'获取gewechat图片下载链接失败: {resp_data}')

                file_url = resp_data['data']['fileUrl']
        except asyncio.TimeoutError:
            raise Exception('获取图片下载链接超时')
        except aiohttp.ClientError as e:
            raise Exception(f'获取图片下载链接网络错误: {str(e)}')

        # 解析原始URL并替换端口
        base_url = gewechat_file_url
        download_url = f'{base_url}/download/{file_url}'

        # 下载图片
        try:
            async with session.get(download_url) as img_response:
                if img_response.status != 200:
                    error = await httpclient.read_text_limited(img_response)
                    raise Exception(f'下载图片失败: {error}, URL: {download_url}')

                image_data = await httpclient.read_limited(img_response)

                content_type = img_response.headers.get('Content-Type', '')
                if content_type:
                    image_format = content_type.split('/')[-1]
                else:
                    image_format = file_url.split('.')[-1]

                base64_str = await encode_base64(image_data)

                return base64_str, image_format
        except asyncio.TimeoutError:
            raise Exception(f'下载图片超时, URL: {download_url}')
        except aiohttp.ClientError as e:
            raise Exception(f'下载图片网络错误: {str(e)}, URL: {download_url}')
    except Exception as e:
        raise Exception(f'获取图片失败: {str(e)}') from e


async def get_wecom_image_base64(pic_url: str) -> tuple[str, str]:
    """
    下载企业微信图片并转换为 base64
    :param pic_url: 企业微信图片URL
    :return: (base64_str, image_format)
    """
    session = httpclient.get_session()
    async with session.get(pic_url) as response:
        if response.status != 200:
            raise Exception(f'Failed to download image: {response.status}')

        # 读取图片数据
        image_data = await httpclient.read_limited(response)

        # 获取图片格式
        content_type = response.headers.get('Content-Type', '')
        image_format = content_type.split('/')[-1]  # 例如 'image/jpeg' -> 'jpeg'

        image_base64 = await encode_base64(image_data)

        return image_base64, image_format


async def get_qq_official_image_base64(pic_url: str, content_type: str) -> tuple[str, str]:
    """
    下载QQ官方图片，
    并且转换为base64格式
    """
    session = httpclient.get_session()
    async with session.get(pic_url) as response:
        response.raise_for_status()
        image_data = await httpclient.read_limited(response)
        base64_data = await encode_base64(image_data)

        return f'data:{content_type};base64,{base64_data}'


def get_qq_image_downloadable_url(image_url: str) -> tuple[str, dict]:
    """获取QQ图片的下载链接"""
    parsed = urlparse(image_url)
    query = parse_qs(parsed.query)
    scheme = parsed.scheme or 'http'
    return f'{scheme}://{parsed.netloc}{parsed.path}', query


async def get_qq_image_bytes(image_url: str, query: dict = {}) -> tuple[bytes, str]:
    """[弃用]获取QQ图片的bytes"""
    image_url, query_in_url = get_qq_image_downloadable_url(image_url)
    query = {**query, **query_in_url}
    session = httpclient.get_session()
    async with session.get(
        image_url,
        params=query,
        ssl=_INSECURE_SSL_CONTEXT,
        timeout=aiohttp.ClientTimeout(total=30.0),
    ) as resp:
        resp.raise_for_status()
        file_bytes = await httpclient.read_limited(resp)
        content_type = resp.headers.get('Content-Type')
        if not content_type:
            image_format = 'jpeg'
        elif not content_type.startswith('image/'):
            image_format = await asyncio.to_thread(_detect_image_format, file_bytes)
        else:
            image_format = content_type.split('/')[-1]
        return file_bytes, image_format


async def qq_image_url_to_base64(image_url: str) -> typing.Tuple[str, str]:
    """[弃用]将QQ图片URL转为base64，并返回图片格式

    Args:
        image_url (str): QQ图片URL

    Returns:
        typing.Tuple[str, str]: base64编码和图片格式
    """
    image_url, query = get_qq_image_downloadable_url(image_url)

    # Flatten the query dictionary
    query = {k: v[0] for k, v in query.items()}

    file_bytes, image_format = await get_qq_image_bytes(image_url, query)

    base64_str = await encode_base64(file_bytes)

    return base64_str, image_format


async def extract_b64_and_format(image_base64_data: str) -> typing.Tuple[str, str]:
    """提取base64编码和图片格式

    data:image/jpeg;base64,xxx
    提取出base64编码和图片格式
    """
    base64_str = image_base64_data.split(',')[-1]
    image_format = image_base64_data.split(':')[-1].split(';')[0].split('/')[-1]
    return base64_str, image_format


async def get_slack_image_to_base64(pic_url: str, bot_token: str):
    headers = {'Authorization': f'Bearer {bot_token}'}
    try:
        session = httpclient.get_session()
        async with session.get(pic_url, headers=headers) as resp:
            mime_type = resp.headers.get('Content-Type', 'application/octet-stream')
            file_bytes = await httpclient.read_limited(resp)
            base64_str = await encode_base64(file_bytes)
        return f'data:{mime_type};base64,{base64_str}'
    except Exception as e:
        raise (e)
