import pip

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
