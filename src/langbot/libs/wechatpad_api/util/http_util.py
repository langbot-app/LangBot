import requests
import aiohttp


def post_json(base_url, token, data=None):
    headers = {'Content-Type': 'application/json'}

    url = base_url + f'?key={token}'

    try:
        response = requests.post(url, json=data, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()

        if result:
            return result
        else:
            raise RuntimeError(response.text)
    except Exception as e:
        print(f'http请求失败, url={url}, exception={e}')
        raise RuntimeError(str(e))


def get_json(base_url, token):
    headers = {'Content-Type': 'application/json'}

    url = base_url + f'?key={token}'

    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()

        if result:
            return result
        else:
            raise RuntimeError(response.text)
    except Exception as e:
        print(f'http请求失败, url={url}, exception={e}')
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
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method=method, url=url, params=params, headers=headers, data=data, json=json
        ) as response:
            response.raise_for_status()  # 如果状态码不是200，抛出异常
            result = await response.json()
            # print(result)
            return result
            # if result.get('Code') == 200:
            #
            #     return await result
            # else:
            #     raise RuntimeError("请求失败",response.text)
