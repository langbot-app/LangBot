import json as json_module

import requests
from langbot.pkg.utils import httpclient

_MAX_WECHATPAD_RESPONSE_BYTES = 16 * 1024 * 1024


def _read_requests_response_limited(response: requests.Response) -> dict:
    content_length = response.headers.get('Content-Length')
    if content_length is not None:
        try:
            if int(content_length) > _MAX_WECHATPAD_RESPONSE_BYTES:
                raise RuntimeError('WeChatPad response exceeds the runtime limit')
        except (TypeError, ValueError):
            pass
    body = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        body.extend(chunk)
        if len(body) > _MAX_WECHATPAD_RESPONSE_BYTES:
            raise RuntimeError('WeChatPad response exceeds the runtime limit')
    result = json_module.loads(body)
    if not isinstance(result, dict):
        raise RuntimeError('WeChatPad returned a non-object response')
    return result


def post_json(base_url, token, data=None):
    headers = {'Content-Type': 'application/json'}

    url = base_url + f'?key={token}'

    try:
        with requests.post(
            url,
            json=data,
            headers=headers,
            timeout=60,
            stream=True,
        ) as response:
            response.raise_for_status()
            result = _read_requests_response_limited(response)

        if result:
            return result
        else:
            raise RuntimeError('WeChatPad returned an empty response')
    except Exception as e:
        raise RuntimeError(str(e))


def get_json(base_url, token):
    headers = {'Content-Type': 'application/json'}

    url = base_url + f'?key={token}'

    try:
        with requests.get(
            url,
            headers=headers,
            timeout=60,
            stream=True,
        ) as response:
            response.raise_for_status()
            result = _read_requests_response_limited(response)

        if result:
            return result
        else:
            raise RuntimeError('WeChatPad returned an empty response')
    except Exception as e:
        raise RuntimeError(str(e))


async def async_request(
    base_url: str,
    token_key: str,
    method: str = 'POST',
    params: dict = None,
    # headers: dict = None,
    data: dict = None,
    json: dict = None,
):
    """
    通用异步请求函数

    :param base_url: 请求URL
    :param token_key: 请求token
    :param method: HTTP方法 (GET, POST, PUT, DELETE等)
    :param params: URL查询参数
    # :param headers: 请求头
    :param data: 表单数据
    :param json: JSON数据
    :return: 响应文本
    """
    headers = {'Content-Type': 'application/json'}
    url = f'{base_url}?key={token_key}'
    session = httpclient.get_session()
    async with session.request(
        method=method, url=url, params=params, headers=headers, data=data, json=json
    ) as response:
        response.raise_for_status()  # 如果状态码不是200，抛出异常
        result = json_module.loads(
            await httpclient.read_limited(
                response,
                max_bytes=_MAX_WECHATPAD_RESPONSE_BYTES,
            )
        )
        # print(result)
        return result
        # if result.get('Code') == 200:
        #
        #     return await result
        # else:
        #     raise RuntimeError("请求失败",response.text)
