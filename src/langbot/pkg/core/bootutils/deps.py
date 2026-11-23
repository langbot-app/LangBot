import importlib.util

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
    'litellm': 'litellm',
    'xxhash': 'xxhash',
}


async def check_deps() -> list[str]:
    global required_deps

    missing_deps = []
    for dep in required_deps:
        # Use find_spec instead of __import__ to avoid actually loading
        # all modules into memory. find_spec only checks if the module
        # can be found, without executing module-level code.
        if importlib.util.find_spec(dep) is None:
            missing_deps.append(dep)
    return missing_deps
