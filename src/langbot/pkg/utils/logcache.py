from __future__ import annotations


LOG_PAGE_SIZE = 20
MAX_CACHED_PAGES = 10


class LogPage:
    """日志页"""

    number: int
    """页码"""

    logs: list[str]

    def __init__(self, number: int):
        self.number = number
        self.logs = []

    def add_log(self, log: str) -> bool:
        """添加日志

        Returns:
            bool: 是否已满
        """
        self.logs.append(log)
        return len(self.logs) >= LOG_PAGE_SIZE


class LogCache:
    """由于 logger 是同步的，但实例中的数据库操作是异步的；
    同时，持久化的日志信息已经写入文件了，故做一个缓存来为前端提供日志查询服务"""

    log_pages: list[LogPage] = []
    """从前到后，越新的日志页越靠后"""

    def __init__(self):
        self.log_pages = []
        self.log_pages.append(LogPage(number=0))

    def add_log(self, log: str):
        """添加日志"""
        if self.log_pages[-1].add_log(log):
            self.log_pages.append(LogPage(number=self.log_pages[-1].number + 1))

            if len(self.log_pages) > MAX_CACHED_PAGES:
                self.log_pages.pop(0)

    def get_log_by_pointer(
        self,
        start_page_number: int,
        start_offset: int,
    ) -> tuple[str, int, int]:
        """获取指定页码和偏移量的日志"""
        final_logs_str = ''

        for page in self.log_pages:
            if page.number == start_page_number:
                final_logs_str += '\n'.join(page.logs[start_offset:])
            elif page.number > start_page_number:
                final_logs_str += '\n'.join(page.logs)

        return final_logs_str, page.number, len(page.logs)
