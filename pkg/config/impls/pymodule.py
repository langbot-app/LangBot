import os
import shutil
import importlib
import logging

from .. import model as file_model


class PythonModuleConfigFile(file_model.ConfigFile):
    """Python模块配置文件"""

    config_file_name: str = None
    """配置文件名"""

    template_file_name: str = None
    """模板文件名"""

    def __init__(self, config_file_name: str, template_file_name: str) -> None:
        self.config_file_name = config_file_name
        self.template_file_name = template_file_name

    def exists(self) -> bool:
        return os.path.exists(self.config_file_name)

    async def create(self):
        shutil.copyfile(self.template_file_name, self.config_file_name)

    async def load(self, completion: bool = True) -> dict:
        module_name = os.path.splitext(os.path.basename(self.config_file_name))[0]
        module = importlib.import_module(module_name)

        cfg = {}

        allowed_types = (int, float, str, bool, list, dict)

        for key in dir(module):
            if key.startswith('__'):
                continue

            if not isinstance(getattr(module, key), allowed_types):
                continue

            cfg[key] = getattr(module, key)

        # 从模板模块文件中进行补全
        if completion:
            module_name = os.path.splitext(os.path.basename(self.template_file_name))[0]
            module = importlib.import_module(module_name)

            for key in dir(module):
                if key.startswith('__'):
                    continue

                if not isinstance(getattr(module, key), allowed_types):
                    continue

                if key not in cfg:
                    cfg[key] = getattr(module, key)

        return cfg

    async def save(self, data: dict):
        logging.warning('Python模块配置文件不支持保存')

    def save_sync(self, data: dict):
        logging.warning('Python模块配置文件不支持保存')
