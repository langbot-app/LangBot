from . import model as file_model
from ..utils import context


class ConfigManager:
    """配置文件管理器"""

    file: file_model.ConfigFile = None
    """配置文件实例"""

    data: dict = None
    """配置数据"""

    def __init__(self, cfg_file: file_model.ConfigFile) -> None:
        self.file = cfg_file
        self.data = {}
        context.set_config_manager(self)

    async def load_config(self):
        self.data = await self.file.load()

    async def dump_config(self):
        await self.file.save(self.data)
