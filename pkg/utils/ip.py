import aiohttp


async def get_myip() -> str:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get('https://ip.useragentinfo.com/myip') as response:
                return await response.text()
    except Exception:
        return '0.0.0.0'
