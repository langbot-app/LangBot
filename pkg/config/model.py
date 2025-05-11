import abc


class ConfigFile(metaclass=abc.ABCMeta):
    """配置文件抽象类"""

    config_file_name: str = None
    """配置文件名"""

    template_file_name: str = None
    """模板文件名"""

    template_data: dict = None
    """模板数据"""

    @abc.abstractmethod
    def exists(self) -> bool:
        pass

    @abc.abstractmethod
    async def create(self):
        pass

    @abc.abstractmethod
    async def load(self, completion: bool = True) -> dict:
        pass

    @abc.abstractmethod
    async def save(self, data: dict):
        pass

    @abc.abstractmethod
    def save_sync(self, data: dict):
        pass
