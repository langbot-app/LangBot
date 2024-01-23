import pip

required_deps = {
    "requests": "requests",
    "openai": "openai",
    "dulwich": "dulwich",
    "colorlog": "colorlog",
    "mirai": "yiri-mirai-rc",
    "func_timeout": "func_timeout",
    "PIL": "pillow",
    "nakuru": "nakuru-project-idk",
    "CallingGPT": "CallingGPT",
    "tiktoken": "tiktoken",
    "yaml": "pyyaml",
    "aiohttp": "aiohttp",
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
