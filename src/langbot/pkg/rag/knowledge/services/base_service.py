# 封装异步操作
import asyncio


class BaseService:
    def __init__(self):
        pass

    async def _run_sync(self, func, *args, **kwargs):
        """
        在单独的线程中运行同步函数。
        如果第一个参数是 session，则在 to_thread 中获取新的 session。
        """

        return await asyncio.to_thread(func, *args, **kwargs)
