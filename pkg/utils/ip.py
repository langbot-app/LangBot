import aiohttp

async def get_myip() -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://ip.useragentinfo.com/myip") as response:
                return await response.text()
    except Exception as e:
        return '0.0.0.0'