import abc
import uuid
import json
import logging
import threading

import requests


class APIGroup(metaclass=abc.ABCMeta):
    """API 组抽象类"""
    _basic_info: dict = None
    _runtime_info: dict = None

    prefix = None

    def __init__(self, prefix: str):
        self.prefix = prefix

    def do(
        self,
        method: str,
        path: str,
        data: dict = None,
        params: dict = None,
        headers: dict = {},
        **kwargs
    ):
        """执行一个请求"""
        def thr_wrapper(
            self,
            method: str,
            path: str,
            data: dict = None,
            params: dict = None,
            headers: dict = {},
            **kwargs
        ):
            try:
                url = self.prefix + path
                data = json.dumps(data)
                headers['Content-Type'] = 'application/json'
                
                ret =  requests.request(
                    method,
                    url,
                    data=data,
                    params=params,
                    headers=headers,
                    **kwargs
                )

                logging.debug("data: %s", data)

                logging.debug("ret: %s", ret.json())
            except Exception as e:
                logging.debug("上报数据失败: %s", e)
        
        thr = threading.Thread(target=thr_wrapper, args=(
            self,
            method,
            path,
            data,
            params,
            headers,
        ), kwargs=kwargs)
        thr.start()

            
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
