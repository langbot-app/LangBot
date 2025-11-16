import base64
import typing
import io
from urllib.parse import urlparse, parse_qs
import ssl

import aiohttp
import PIL.Image
import httpx

import asyncio


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
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 获取图片下载链接
            try:
                async with session.post(
                    f'{gewechat_url}/v2/api/message/downloadImage',
                    headers=headers,
                    json={'appId': app_id, 'type': image_type, 'xml': xml_content},
                ) as response:
                    if response.status != 200:
                        # print(response)
                        raise Exception(f'获取gewechat图片下载失败: {await response.text()}')

                    resp_data = await response.json()
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
                        raise Exception(f'下载图片失败: {await img_response.text()}, URL: {download_url}')

                    image_data = await img_response.read()

                    content_type = img_response.headers.get('Content-Type', '')
                    if content_type:
                        image_format = content_type.split('/')[-1]
                    else:
                        image_format = file_url.split('.')[-1]

                    base64_str = base64.b64encode(image_data).decode('utf-8')

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
    async with aiohttp.ClientSession() as session:
        async with session.get(pic_url) as response:
            if response.status != 200:
                raise Exception(f'Failed to download image: {response.status}')

            # 读取图片数据
            image_data = await response.read()

            # 获取图片格式
            content_type = response.headers.get('Content-Type', '')
            image_format = content_type.split('/')[-1]  # 例如 'image/jpeg' -> 'jpeg'

            # 转换为 base64
            import base64

            image_base64 = base64.b64encode(image_data).decode('utf-8')

            return image_base64, image_format


async def get_qq_official_image_base64(pic_url: str, content_type: str) -> tuple[str, str]:
    """
    下载QQ官方图片，
    并且转换为base64格式
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(pic_url)
        response.raise_for_status()  # 确保请求成功
        image_data = response.content
        base64_data = base64.b64encode(image_data).decode('utf-8')

        return f'data:{content_type};base64,{base64_data}'


def get_qq_image_downloadable_url(image_url: str) -> tuple[str, dict]:
    """获取QQ图片的下载链接"""
    parsed = urlparse(image_url)
    query = parse_qs(parsed.query)
    return f'http://{parsed.netloc}{parsed.path}', query


async def get_qq_image_bytes(image_url: str, query: dict = {}) -> tuple[bytes, str]:
    """[弃用]获取QQ图片的bytes"""
    image_url, query_in_url = get_qq_image_downloadable_url(image_url)
    query = {**query, **query_in_url}
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    async with aiohttp.ClientSession(trust_env=False) as session:
        async with session.get(image_url, params=query, ssl=ssl_context) as resp:
            resp.raise_for_status()
            file_bytes = await resp.read()
            content_type = resp.headers.get('Content-Type')
            if not content_type:
                image_format = 'jpeg'
            elif not content_type.startswith('image/'):
                pil_img = PIL.Image.open(io.BytesIO(file_bytes))
                image_format = pil_img.format.lower()
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

    base64_str = base64.b64encode(file_bytes).decode()

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
        async with aiohttp.ClientSession() as session:
            async with session.get(pic_url, headers=headers) as resp:
                mime_type = resp.headers.get('Content-Type', 'application/octet-stream')
                file_bytes = await resp.read()
                base64_str = base64.b64encode(file_bytes).decode('utf-8')
            return f'data:{mime_type};base64,{base64_str}'
    except Exception as e:
        raise (e)
