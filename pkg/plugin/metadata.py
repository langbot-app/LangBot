import os
import shutil
import json
import time

import dulwich.errors as dulwich_err

from ..utils import updater


def read_metadata_file() -> dict:
    # 读取 plugins/metadata.json 文件
    if not os.path.exists('plugins/metadata.json'):
        return {}
    with open('plugins/metadata.json', 'r') as f:
        return json.load(f)


def write_metadata_file(metadata: dict):
    if not os.path.exists('plugins'):
        os.mkdir('plugins')

    with open('plugins/metadata.json', 'w') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)


def do_plugin_git_repo_migrate():
    # 仅在 plugins/metadata.json 不存在时执行
    if os.path.exists('plugins/metadata.json'):
        return

    metadata = read_metadata_file()

    # 遍历 plugins 下所有目录，获取目录的git远程地址
    for plugin_name in os.listdir('plugins'):
        plugin_path = os.path.join('plugins', plugin_name)
        if not os.path.isdir(plugin_path):
            continue
        
        remote_url = None
        try:
            remote_url = updater.get_remote_url(plugin_path)
        except dulwich_err.NotGitRepository:
            continue
        if remote_url == "https://github.com/RockChinQ/QChatGPT" or remote_url == "https://gitee.com/RockChin/QChatGPT" \
            or remote_url == "" or remote_url is None or remote_url == "http://github.com/RockChinQ/QChatGPT" or remote_url == "http://gitee.com/RockChin/QChatGPT":
            continue

        from . import host

        if plugin_name not in metadata:
            metadata[plugin_name] = {
                'source': remote_url,
                'install_timestamp': int(time.time()),
                'ref': 'HEAD',
            }

    write_metadata_file(metadata)
    

def set_plugin_metadata(
    plugin_name: str,
    source: str,
    install_timestamp: int,
    ref: str,
):
    metadata = read_metadata_file()
    metadata[plugin_name] = {
        'source': source,
        'install_timestamp': install_timestamp,
        'ref': ref,
    }
    write_metadata_file(metadata)


def remove_plugin_metadata(plugin_name: str):
    metadata = read_metadata_file()
    if plugin_name in metadata:
        del metadata[plugin_name]
        write_metadata_file(metadata)


def get_plugin_metadata(plugin_name: str) -> dict:
    metadata = read_metadata_file()
    if plugin_name in metadata:
        return metadata[plugin_name]
    return {}