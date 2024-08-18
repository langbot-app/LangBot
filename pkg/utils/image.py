import base64
import typing
from urllib.parse import urlparse, parse_qs
import ssl

import aiohttp


async def qq_image_url_to_base64(
    image_url: str
) -> typing.Tuple[str, str]:
    """将QQ图片URL转为base64，并返回图片格式

    Args:
        image_url (str): QQ图片URL

    Returns:
        typing.Tuple[str, str]: base64编码和图片格式
    """
    parsed = urlparse(image_url)
    query = parse_qs(parsed.query)

    # Flatten the query dictionary
    query = {k: v[0] for k, v in query.items()}

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(trust_env=False) as session:
        async with session.get(
            f"http://{parsed.netloc}{parsed.path}",
            params=query,
            ssl=ssl_context
        ) as resp:
            resp.raise_for_status()  # 检查HTTP错误
            file_bytes = await resp.read()
            content_type = resp.headers.get('Content-Type')
            if not content_type or not content_type.startswith('image/'):
                image_format = 'jpeg'
            else: 
                image_format = content_type.split('/')[-1]

    base64_str = base64.b64encode(file_bytes).decode()

    return base64_str, image_format
