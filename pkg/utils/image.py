import base64
import typing
from urllib.parse import urlparse, parse_qs
import ssl

import aiohttp


def get_qq_image_downloadable_url(image_url: str) -> tuple[str, dict]:
    """获取QQ图片的下载链接"""
    parsed = urlparse(image_url)
    query = parse_qs(parsed.query)
    return f"http://{parsed.netloc}{parsed.path}", query


async def get_qq_image_bytes(image_url: str) -> tuple[bytes, str]:
    """获取QQ图片的bytes"""
    image_url, query = get_qq_image_downloadable_url(image_url)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    async with aiohttp.ClientSession(trust_env=False) as session:
        async with session.get(image_url, params=query, ssl=ssl_context) as resp:
            resp.raise_for_status()
            file_bytes = await resp.read()
            content_type = resp.headers.get('Content-Type')
            if not content_type or not content_type.startswith('image/'):
                image_format = 'jpeg'
            else: 
                image_format = content_type.split('/')[-1]
            return file_bytes, image_format


async def qq_image_url_to_base64(
    image_url: str
) -> typing.Tuple[str, str]:
    """将QQ图片URL转为base64，并返回图片格式

    Args:
        image_url (str): QQ图片URL

    Returns:
        typing.Tuple[str, str]: base64编码和图片格式
    """
    image_url, query = get_qq_image_downloadable_url(image_url)

    # Flatten the query dictionary
    query = {k: v[0] for k, v in query.items()}

    file_bytes, image_format = await get_qq_image_bytes(image_url)

    base64_str = base64.b64encode(file_bytes).decode()

    return base64_str, image_format
