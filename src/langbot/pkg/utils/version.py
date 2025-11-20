from __future__ import annotations

import os
import typing
import logging

import requests

from ..core import app
from . import constants


class VersionManager:
    """版本管理器"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    def get_current_version(self) -> str:
        current_tag = constants.semantic_version

        return current_tag

    async def get_release_list(self) -> list:
        """获取发行列表"""
        try:
            rls_list_resp = requests.get(
                url='https://api.github.com/repos/langbot-app/LangBot/releases',
                proxies=self.ap.proxy_mgr.get_forward_proxies(),
                timeout=5,
            )
            rls_list_resp.raise_for_status()  # 检查请求是否成功
            rls_list = rls_list_resp.json()
            return rls_list
        except Exception as e:
            self.ap.logger.warning(f'获取发行列表失败: {e}')
            pass
        return []

    async def update_all(self):
        """检查更新并下载源码"""

        current_tag = self.get_current_version()

        rls_list = await self.get_release_list()

        latest_rls = {}
        rls_notes = []
        latest_tag_name = ''
        for rls in rls_list:
            rls_notes.append(rls['name'])  # 使用发行名称作为note
            if latest_tag_name == '':
                latest_tag_name = rls['tag_name']

            if rls['tag_name'] == current_tag:
                break

            if latest_rls == {}:
                latest_rls = rls
        self.ap.logger.info('更新日志: {}'.format(rls_notes))

        if latest_rls == {} and not self.is_newer(latest_tag_name, current_tag):  # 没有新版本
            return False

        # 下载最新版本的zip到temp目录
        self.ap.logger.info('开始下载最新版本: {}'.format(latest_rls['zipball_url']))

        zip_url = latest_rls['zipball_url']
        zip_resp = requests.get(url=zip_url, proxies=self.ap.proxy_mgr.get_forward_proxies())
        zip_data = zip_resp.content

        # 检查temp/updater目录
        if not os.path.exists('temp'):
            os.mkdir('temp')
        if not os.path.exists('temp/updater'):
            os.mkdir('temp/updater')
        with open('temp/updater/{}.zip'.format(latest_rls['tag_name']), 'wb') as f:
            f.write(zip_data)

        self.ap.logger.info('下载最新版本完成: {}'.format('temp/updater/{}.zip'.format(latest_rls['tag_name'])))

        # 解压zip到temp/updater/<tag_name>/
        import zipfile

        # 检查目标文件夹
        if os.path.exists('temp/updater/{}'.format(latest_rls['tag_name'])):
            import shutil

            shutil.rmtree('temp/updater/{}'.format(latest_rls['tag_name']))
        os.mkdir('temp/updater/{}'.format(latest_rls['tag_name']))
        with zipfile.ZipFile('temp/updater/{}.zip'.format(latest_rls['tag_name']), 'r') as zip_ref:
            zip_ref.extractall('temp/updater/{}'.format(latest_rls['tag_name']))

        # 覆盖源码
        source_root = ''
        # 找到temp/updater/<tag_name>/中的第一个子目录路径
        for root, dirs, files in os.walk('temp/updater/{}'.format(latest_rls['tag_name'])):
            if root != 'temp/updater/{}'.format(latest_rls['tag_name']):
                source_root = root
                break

        # 覆盖源码
        import shutil

        for root, dirs, files in os.walk(source_root):
            # 覆盖所有子文件子目录
            for file in files:
                src = os.path.join(root, file)
                dst = src.replace(source_root, '.')
                if os.path.exists(dst):
                    os.remove(dst)

                # 检查目标文件夹是否存在
                if not os.path.exists(os.path.dirname(dst)):
                    os.makedirs(os.path.dirname(dst))
                # 检查目标文件是否存在
                if not os.path.exists(dst):
                    # 创建目标文件
                    open(dst, 'w').close()

                shutil.copy(src, dst)

        # 把current_tag写入文件
        current_tag = latest_rls['tag_name']
        with open('current_tag', 'w') as f:
            f.write(current_tag)

        # TODO statistics

    async def is_new_version_available(self) -> bool:
        """检查是否有新版本"""
        # 从github获取release列表
        rls_list = await self.get_release_list()
        if rls_list is None:
            return False

        # 获取当前版本
        current_tag = self.get_current_version()

        # 检查是否有新版本
        latest_tag_name = ''
        for rls in rls_list:
            if latest_tag_name == '':
                latest_tag_name = rls['tag_name']
                break

        return self.is_newer(latest_tag_name, current_tag)

    def is_newer(self, new_tag: str, old_tag: str):
        """判断版本是否更新，忽略第四位版本和第一位版本"""
        if new_tag == old_tag:
            return False

        new_tag = new_tag.split('.')
        old_tag = old_tag.split('.')

        # 判断主版本是否相同
        if new_tag[0] != old_tag[0]:
            return False

        if len(new_tag) < 4:
            return True

        # 合成前三段，判断是否相同
        new_tag = '.'.join(new_tag[:3])
        old_tag = '.'.join(old_tag[:3])

        return new_tag != old_tag

    def compare_version_str(v0: str, v1: str) -> int:
        """比较两个版本号"""

        # 删除版本号前的v
        if v0.startswith('v'):
            v0 = v0[1:]
        if v1.startswith('v'):
            v1 = v1[1:]

        v0: list = v0.split('.')
        v1: list = v1.split('.')

        # 如果两个版本号节数不同，把短的后面用0补齐
        if len(v0) < len(v1):
            v0.extend(['0'] * (len(v1) - len(v0)))
        elif len(v0) > len(v1):
            v1.extend(['0'] * (len(v0) - len(v1)))

        # 从高位向低位比较
        for i in range(len(v0)):
            if int(v0[i]) > int(v1[i]):
                return 1
            elif int(v0[i]) < int(v1[i]):
                return -1

        return 0

    async def show_version_update(self) -> typing.Tuple[str, int]:
        try:
            if await self.ap.ver_mgr.is_new_version_available():
                return (
                    'New version available:\n有新版本可用，根据文档更新: \nhttps://docs.langbot.app/zh/deploy/update.html',
                    logging.INFO,
                )

        except Exception as e:
            return f'Error checking version update: {e}', logging.WARNING
