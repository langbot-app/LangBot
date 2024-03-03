from __future__ import annotations

import re
import os
import shutil
import zipfile

import requests

from .. import installer, errors
from ...utils import pkgmgr


class GitHubRepoInstaller(installer.PluginInstaller):
    """GitHub仓库插件安装器
    """

    def get_github_plugin_repo_label(self, repo_url: str) -> list[str]:
        """获取username, repo"""

        # 提取 username/repo , 正则表达式
        repo = re.findall(
            r"(?:https?://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git|/|$)",
            repo_url,
        )

        if len(repo) > 0:  # github
            return repo[0].split("/")
        else:
            return None
        
    async def download_plugin_source_code(self, repo_url: str, target_path: str) -> str:
        """下载插件源码"""
        # 检查源类型

        # 提取 username/repo , 正则表达式
        repo = self.get_github_plugin_repo_label(repo_url)

        target_path += repo[1]

        if repo is not None:  # github
            self.ap.logger.debug("正在下载源码...")

            zipball_url = f"https://api.github.com/repos/{'/'.join(repo)}/zipball/HEAD"

            zip_resp = requests.get(
                url=zipball_url, proxies=self.ap.proxy_mgr.get_forward_proxies(), stream=True
            )

            if zip_resp.status_code != 200:
                raise Exception("下载源码失败: {}".format(zip_resp.text))

            if os.path.exists("temp/" + target_path):
                shutil.rmtree("temp/" + target_path)

            if os.path.exists(target_path):
                shutil.rmtree(target_path)

            os.makedirs("temp/" + target_path)

            with open("temp/" + target_path + "/source.zip", "wb") as f:
                for chunk in zip_resp.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

            self.ap.logger.debug("解压中...")

            with zipfile.ZipFile("temp/" + target_path + "/source.zip", "r") as zip_ref:
                zip_ref.extractall("temp/" + target_path)
            os.remove("temp/" + target_path + "/source.zip")

            # 目标是 username-repo-hash , 用正则表达式提取完整的文件夹名，复制到 plugins/repo
            import glob

            # 获取解压后的文件夹名
            unzip_dir = glob.glob("temp/" + target_path + "/*")[0]

            # 复制到 plugins/repo
            shutil.copytree(unzip_dir, target_path + "/")

            # 删除解压后的文件夹
            shutil.rmtree(unzip_dir)
            
            self.ap.logger.debug("源码下载完成。")
        else:
            raise errors.PluginInstallerError('仅支持GitHub仓库地址')

        return repo[1]
    
    async def install_requirements(self, path: str):
        if os.path.exists(path + "/requirements.txt"):
            pkgmgr.install_requirements(path + "/requirements.txt")

    async def install_plugin(
        self,
        plugin_source: str,
    ):
        """安装插件
        """
        repo_label = await self.download_plugin_source_code(plugin_source, "plugins/")

        await self.install_requirements("plugins/" + repo_label)

        await self.ap.plugin_mgr.setting.record_installed_plugin_source(
            "plugins/"+repo_label+'/', plugin_source
        )

    async def uninstall_plugin(
        self,
        plugin_name: str,
    ):
        """卸载插件
        """
        plugin_container = self.ap.plugin_mgr.get_plugin_by_name(plugin_name)

        if plugin_container is None:
            raise errors.PluginInstallerError('插件不存在或未成功加载')
        else:
            shutil.rmtree(plugin_container.pkg_path)

    async def update_plugin(
        self,
        plugin_name: str,
        plugin_source: str=None,
    ):
        """更新插件
        """
        plugin_container = self.ap.plugin_mgr.get_plugin_by_name(plugin_name)

        if plugin_container is None:
            raise errors.PluginInstallerError('插件不存在或未成功加载')
        else:
            if plugin_container.plugin_source:
                plugin_source = plugin_container.plugin_source

                await self.install_plugin(plugin_source)

            else:
                raise errors.PluginInstallerError('插件无源码信息，无法更新')
