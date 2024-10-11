from __future__ import annotations

import pydantic


LOG_PAGE_SIZE = 20
MAX_CACHED_PAGES = 10


class LogPage(pydantic.BaseModel):
    """日志页"""

    cached_count: int = 0

    logs: str = ""

    def add_log(self, log: str) -> bool:
        """添加日志

        Returns:
            bool: 是否已满
        """
        self.logs += log
        self.cached_count += 1
        return self.cached_count >= LOG_PAGE_SIZE


class LogCache:
    """由于 logger 是同步的，但实例中的数据库操作是异步的；
    同时，持久化的日志信息已经写入文件了，故做一个缓存来为前端提供日志查询服务"""

    log_pages: list[LogPage] = []
    """从前到后，越新的日志页越靠后"""

    def __init__(self):
        self.log_pages = []
        self.log_pages.append(LogPage())

    def add_log(self, log: str):
        """添加日志"""
        if self.log_pages[-1].add_log(log):
            self.log_pages.append(LogPage())

            if len(self.log_pages) > MAX_CACHED_PAGES:
                self.log_pages.pop(0)

    def get_all_logs(self) -> str:
        """获取所有日志"""
        return "".join([page.logs for page in self.log_pages])
