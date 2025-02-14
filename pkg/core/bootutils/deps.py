import pip

# 检查依赖，防止用户未安装
# 左边为引入名称，右边为依赖名称
required_deps = {
    "requests": "requests",
    "openai": "openai",
    "anthropic": "anthropic",
    "colorlog": "colorlog",
    "aiocqhttp": "aiocqhttp",
    "botpy": "qq-botpy-rc",
    "PIL": "pillow",
    "nakuru": "nakuru-project-idk",
    "tiktoken": "tiktoken",
    "yaml": "pyyaml",
    "aiohttp": "aiohttp",
    "psutil": "psutil",
    "async_lru": "async-lru",
    "ollama": "ollama",
    "quart": "quart",
    "quart_cors": "quart-cors",
    "sqlalchemy": "sqlalchemy[asyncio]",
    "aiosqlite": "aiosqlite",
    "aiofiles": "aiofiles",
    "aioshutil": "aioshutil",
    "argon2": "argon2-cffi",
    "jwt": "pyjwt",
    "Crypto": "pycryptodome",
    "lark_oapi": "lark-oapi",
    "discord": "discord.py",
    "cryptography": "cryptography",
    "gewechat_client": "gewechat-client",
    "dingtalk_stream": "dingtalk_stream",
    "dashscope": "dashscope",
    "telegram": "python-telegram-bot",
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
        pip.main(["install", required_deps[dep]])
