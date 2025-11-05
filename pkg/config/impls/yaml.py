import os
import shutil
import yaml

from .. import model as file_model


class YAMLConfigFile(file_model.ConfigFile):
    """YAML config file"""

    def __init__(
        self,
        config_file_name: str,
        template_file_name: str = None,
        template_data: dict = None,
    ) -> None:
        self.config_file_name = config_file_name
        self.template_file_name = template_file_name
        self.template_data = template_data

    def exists(self) -> bool:
        return os.path.exists(self.config_file_name)

    async def create(self):
        if self.template_file_name is not None:
            shutil.copyfile(self.template_file_name, self.config_file_name)
        elif self.template_data is not None:
            with open(self.config_file_name, 'w', encoding='utf-8') as f:
                yaml.dump(self.template_data, f, indent=4, allow_unicode=True)
        else:
            raise ValueError('template_file_name or template_data must be provided')

    async def load(self, completion: bool = True) -> dict:
        if not self.exists():
            await self.create()

        if self.template_file_name is not None:
            with open(self.template_file_name, 'r', encoding='utf-8') as f:
                self.template_data = yaml.load(f, Loader=yaml.FullLoader)

        with open(self.config_file_name, 'r', encoding='utf-8') as f:
            try:
                cfg = yaml.load(f, Loader=yaml.FullLoader)
            except yaml.YAMLError as e:
                raise Exception(f'Syntax error in config file {self.config_file_name}: {e}')

        if completion:
            for key in self.template_data:
                if key not in cfg:
                    cfg[key] = self.template_data[key]

        return cfg

    async def save(self, cfg: dict):
        with open(self.config_file_name, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, indent=4, allow_unicode=True)

    def save_sync(self, cfg: dict):
        with open(self.config_file_name, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, indent=4, allow_unicode=True)
