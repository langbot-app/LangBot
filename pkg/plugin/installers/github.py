from __future__ import annotations

import re
import os
import zipfile
import ssl
import certifi

import aiohttp
import aiofiles
import aiofiles.os as aiofiles_os
import aioshutil

from .. import installer, errors
from ...utils import pkgmgr
from ...core import taskmgr


class GitHubRepoInstaller(installer.PluginInstaller):
    """GitHub仓库插件安装器"""

    def get_github_plugin_repo_label(self, repo_url: str) -> list[str]:
        """获取username, repo"""
        repo = re.findall(
            r'(?:https?://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git|/|$)',
            repo_url,
        )
        if len(repo) > 0:
            return repo[0].split('/')
        else:
            return None

    async def download_plugin_source_code(
        self,
        repo_url: str,
        target_path: str,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ) -> str:
        """下载插件源码（全异步）"""
        repo = self.get_github_plugin_repo_label(repo_url)
        if repo is None:
            raise errors.PluginInstallerError('仅支持GitHub仓库地址')

        target_path += repo[1]
        self.ap.logger.debug('正在下载源码...')
        task_context.trace('下载源码...', 'download-plugin-source-code')

        zipball_url = f'https://api.github.com/repos/{"/".join(repo)}/zipball/HEAD'
        zip_resp: bytes = None

        # 创建自定义SSL上下文，使用certifi提供的根证书
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(
                url=zipball_url,
                timeout=aiohttp.ClientTimeout(total=300),
                ssl=ssl_context,  # 使用自定义SSL上下文来验证证书
            ) as resp:
                if resp.status != 200:
                    raise errors.PluginInstallerError(f'下载源码失败: {await resp.text()}')
                zip_resp = await resp.read()

        if await aiofiles_os.path.exists('temp/' + target_path):
            await aioshutil.rmtree('temp/' + target_path)

        if await aiofiles_os.path.exists(target_path):
            await aioshutil.rmtree(target_path)

        await aiofiles_os.makedirs('temp/' + target_path)

        async with aiofiles.open('temp/' + target_path + '/source.zip', 'wb') as f:
            await f.write(zip_resp)

        self.ap.logger.debug('解压中...')
        task_context.trace('解压中...', 'unzip-plugin-source-code')

        with zipfile.ZipFile('temp/' + target_path + '/source.zip', 'r') as zip_ref:
            zip_ref.extractall('temp/' + target_path)
        await aiofiles_os.remove('temp/' + target_path + '/source.zip')

        import glob

        unzip_dir = glob.glob('temp/' + target_path + '/*')[0]
        await aioshutil.copytree(unzip_dir, target_path + '/')
        await aioshutil.rmtree(unzip_dir)

        self.ap.logger.debug('源码下载完成。')
        return repo[1]

    async def install_requirements(self, path: str):
        if os.path.exists(path + '/requirements.txt'):
            pkgmgr.install_requirements(path + '/requirements.txt')

    async def install_plugin(
        self,
        plugin_source: str,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """安装插件"""
        task_context.trace('下载插件源码...', 'install-plugin')
        repo_label = await self.download_plugin_source_code(plugin_source, 'plugins/', task_context)
        task_context.trace('安装插件依赖...', 'install-plugin')
        await self.install_requirements('plugins/' + repo_label)
        task_context.trace('完成.', 'install-plugin')

        # Caution: in the v4.0, plugin without manifest will not be able to be updated
        # await self.ap.plugin_mgr.setting.record_installed_plugin_source(
        #     "plugins/" + repo_label + '/', plugin_source
        # )

    async def uninstall_plugin(
        self,
        plugin_name: str,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """卸载插件"""
        plugin_container = self.ap.plugin_mgr.get_plugin_by_name(plugin_name)
        if plugin_container is None:
            raise errors.PluginInstallerError('插件不存在或未成功加载')
        else:
            task_context.trace('删除插件目录...', 'uninstall-plugin')
            await aioshutil.rmtree(plugin_container.pkg_path)
            task_context.trace('完成, 重新加载以生效.', 'uninstall-plugin')

    async def update_plugin(
        self,
        plugin_name: str,
        plugin_source: str = None,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """更新插件"""
        task_context.trace('更新插件...', 'update-plugin')
        plugin_container = self.ap.plugin_mgr.get_plugin_by_name(plugin_name)
        if plugin_container is None:
            raise errors.PluginInstallerError('插件不存在或未成功加载')
        else:
            if plugin_container.plugin_repository:
                plugin_source = plugin_container.plugin_repository
                task_context.trace('转交安装任务.', 'update-plugin')
                await self.install_plugin(plugin_source, task_context)
            else:
                raise errors.PluginInstallerError('插件无源码信息，无法更新')
