from __future__ import annotations

import abc
import uuid
import json
import logging
import asyncio

import aiohttp
import requests

from ...core import app


class APIGroup(metaclass=abc.ABCMeta):
    """API 组抽象类"""
    _basic_info: dict = None
    _runtime_info: dict = None

    prefix = None

    ap: app.Application

    def __init__(self, prefix: str, ap: app.Application):
        self.prefix = prefix
        self.ap = ap

    async def _do(
        self,
        method: str,
        path: str,
        data: dict = None,
        params: dict = None,
        headers: dict = {},
        **kwargs
    ):
        """
        执行请求
        """
        self._runtime_info['account_id'] = "-1"
        
        url = self.prefix + path
        data = json.dumps(data)
        headers['Content-Type'] = 'application/json'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    data=data,
                    params=params,
                    headers=headers,
                    **kwargs
                ) as resp:
                    self.ap.logger.debug("data: %s", data)
                    self.ap.logger.debug("ret: %s", await resp.text())

        except Exception as e:
            self.ap.logger.debug(f'上报失败: {e}')
    
    async def do(
        self,
        method: str,
        path: str,
        data: dict = None,
        params: dict = None,
        headers: dict = {},
        **kwargs
    ) -> asyncio.Task:
        """执行请求"""
        asyncio.create_task(self._do(method, path, data, params, headers, **kwargs))

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
        return basic_info
    
    def runtime_info(
        self
    ):
        """获取运行时信息"""
        return APIGroup._runtime_info
