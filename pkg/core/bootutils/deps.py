import pip
import os
from ...utils import pkgmgr

# 检查依赖，防止用户未安装
# 左边为引入名称，右边为依赖名称
required_deps = {
    'requests': 'requests',
    'openai': 'openai',
    'anthropic': 'anthropic',
    'colorlog': 'colorlog',
    'aiocqhttp': 'aiocqhttp',
    'botpy': 'qq-botpy-rc',
    'PIL': 'pillow',
    'nakuru': 'nakuru-project-idk',
    'tiktoken': 'tiktoken',
    'yaml': 'pyyaml',
    'aiohttp': 'aiohttp',
    'psutil': 'psutil',
    'async_lru': 'async-lru',
    'ollama': 'ollama',
    'quart': 'quart',
    'quart_cors': 'quart-cors',
    'sqlalchemy': 'sqlalchemy[asyncio]',
    'aiosqlite': 'aiosqlite',
    'aiofiles': 'aiofiles',
    'aioshutil': 'aioshutil',
    'argon2': 'argon2-cffi',
    'jwt': 'pyjwt',
    'Crypto': 'pycryptodome',
    'lark_oapi': 'lark-oapi',
    'discord': 'discord.py',
    'cryptography': 'cryptography',
    'gewechat_client': 'gewechat-client',
    'dingtalk_stream': 'dingtalk_stream',
    'dashscope': 'dashscope',
    'telegram': 'python-telegram-bot',
    'certifi': 'certifi',
    'mcp': 'mcp',
    'sqlmodel': 'sqlmodel',
    'telegramify_markdown': 'telegramify-markdown',
    'slack_sdk': 'slack_sdk',
}


async def check_deps() -> list[str]:
    global required_deps

    missing_deps = []
    for dep in required_deps:
        try:
            __import__(dep)
        except ImportError:
            missing_deps.append(dep)
    return missing_deps


async def install_deps(deps: list[str]):
    global required_deps

    for dep in deps:
        pip.main(['install', required_deps[dep]])


async def precheck_plugin_deps():
    print('[Startup] Prechecking plugin dependencies...')

    # 只有在plugins目录存在时才执行插件依赖安装
    if os.path.exists('plugins'):
        for dir in os.listdir('plugins'):
            subdir = os.path.join('plugins', dir)
            if not os.path.isdir(subdir):
                continue
            if 'requirements.txt' in os.listdir(subdir):
                pkgmgr.install_requirements(
                    os.path.join(subdir, 'requirements.txt'),
                    extra_params=['-q', '-q', '-q'],
                )
