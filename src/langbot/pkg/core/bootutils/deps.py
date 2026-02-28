import pip
import os
from ...utils import pkgmgr

# Check dependencies to prevent users from not installing
# Left is the import name, right is the dependency name
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
    'asyncpg': 'asyncpg',
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

    # Only execute plugin dependency installation when the plugins directory exists
    if os.path.exists('plugins'):
        for dir in os.listdir('plugins'):
            subdir = os.path.join('plugins', dir)
            if not os.path.isdir(subdir):
                continue
            if 'requirements.txt' in os.listdir(subdir):
                pkgmgr.install_requirements(
                    os.path.join(subdir, 'requirements.txt'),
                    extra_params=[],
                )
