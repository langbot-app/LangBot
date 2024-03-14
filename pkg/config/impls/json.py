import os
import shutil
import json

from .. import model as file_model


class JSONConfigFile(file_model.ConfigFile):
    """JSON配置文件"""

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

    async def load(self) -> dict:

        if not self.exists():
            await self.create()

        with open(self.config_file_name, 'r', encoding='utf-8') as f:
            cfg = json.load(f)

        # 从模板文件中进行补全
        with open(self.template_file_name, 'r', encoding='utf-8') as f:
            template_cfg = json.load(f)

        for key in template_cfg:
            if key not in cfg:
                cfg[key] = template_cfg[key]

        return cfg
    
    async def save(self, cfg: dict):
        with open(self.config_file_name, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def save_sync(self, cfg: dict):
        with open(self.config_file_name, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)