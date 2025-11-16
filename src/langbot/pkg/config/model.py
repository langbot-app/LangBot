import abc


class ConfigFile(metaclass=abc.ABCMeta):
    """Config file abstract class"""

    config_file_name: str = None
    """Config file name"""

    template_file_name: str = None
    """Template file name"""

    template_data: dict = None
    """Template data"""

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
