from __future__ import annotations

import os

import requests

from ..core import app
from . import constants


class VersionManager:

    ap: app.Application

    def __init__(
        self,
        ap: app.Application
    ):
        self.ap = ap

    async def initialize(
        self
    ):
        pass
    
    def get_current_version(
        self
    ) -> str:
        current_tag = constants.semantic_version
        if os.path.exists("current_tag"):
            with open("current_tag", "r") as f:
                current_tag = f.read()

        return current_tag
    
    async def get_current_version_info(
        self
    ) -> str:
            
        """获取当前版本信息"""
        rls_list = await self.get_release_list()
        current_tag = self.get_current_version()
        for rls in rls_list:
            if rls['tag_name'] == current_tag:
                return rls['name'] + "\n" + rls['body']
        return "未知版本"
    
    async def get_release_list(self) -> list:
        """获取发行列表"""
        rls_list_resp = requests.get(
            url="https://api.github.com/repos/RockChinQ/QChatGPT/releases",
            proxies=self.ap.proxy_mgr.get_forward_proxies()
        )

        rls_list = rls_list_resp.json()

        return rls_list
    
    async def update_all(self):
        pass

    async def is_new_version_available(self) -> bool:
        """检查是否有新版本"""
        # 从github获取release列表
        rls_list = await self.get_release_list()
        if rls_list is None:
            return False

        # 获取当前版本
        current_tag = self.get_current_version()

        # 检查是否有新版本
        latest_tag_name = ""
        for rls in rls_list:
            if latest_tag_name == "":
                latest_tag_name = rls['tag_name']
                break

        return self.is_newer(latest_tag_name, current_tag)
    

    def is_newer(self, new_tag: str, old_tag: str):
        """判断版本是否更新，忽略第四位版本和第一位版本"""
        if new_tag == old_tag:
            return False

        new_tag = new_tag.split(".")
        old_tag = old_tag.split(".")
        
        # 判断主版本是否相同
        if new_tag[0] != old_tag[0]:
            return False

        if len(new_tag) < 4:
            return True

        # 合成前三段，判断是否相同
        new_tag = ".".join(new_tag[:3])
        old_tag = ".".join(old_tag[:3])

        return new_tag != old_tag


    def compare_version_str(v0: str, v1: str) -> int:
        """比较两个版本号"""

        # 删除版本号前的v
        if v0.startswith("v"):
            v0 = v0[1:]
        if v1.startswith("v"):
            v1 = v1[1:]

        v0:list = v0.split(".")
        v1:list = v1.split(".")

        # 如果两个版本号节数不同，把短的后面用0补齐
        if len(v0) < len(v1):
            v0.extend(["0"]*(len(v1)-len(v0)))
        elif len(v0) > len(v1):
            v1.extend(["0"]*(len(v0)-len(v1)))

        # 从高位向低位比较
        for i in range(len(v0)):
            if int(v0[i]) > int(v1[i]):
                return 1
            elif int(v0[i]) < int(v1[i]):
                return -1
        
        return 0

