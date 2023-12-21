import abc
import uuid
import json

import aiohttp


class APIGroup(metaclass=abc.ABCMeta):
    """API 组抽象类"""
    _basic_info: dict = None
    _runtime_info: dict = None

    prefix = None

    def __init__(self, prefix: str):
        self.prefix = prefix

    async def do(
        self,
        method: str,
        path: str,
        data: dict = None,
        params: dict = None,
        headers: dict = None,
        **kwargs
    ):
        """执行一个请求"""
        url = self.prefix + path
        data = json.dumps(data)
        headers['Content-Type'] = 'application/json'
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                data=data,
                params=params,
                headers=headers,
                **kwargs
            ) as resp:
                return await resp.json()
            
    def gen_rid(
        self
    ):
        """生成一个请求 ID"""
        return str(uuid.uuid4())

    def basic_info(
        self
    ):
        """获取基本信息"""
        basic_info = APIGroup._basic_info.copy()
        basic_info['rid'] = self.gen_rid()
        return APIGroup._basic_info
    
    def runtime_info(
        self
    ):
        """获取运行时信息"""
        return APIGroup._runtime_info
