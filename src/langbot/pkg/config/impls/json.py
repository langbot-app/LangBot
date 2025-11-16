import os
import json
import importlib.resources as resources

from langbot.pkg.config import model as file_model


class JSONConfigFile(file_model.ConfigFile):
    """JSON config file"""

    def __init__(
        self,
        config_file_name: str,
        template_resource_name: str = None,
        template_data: dict = None,
    ) -> None:
        self.config_file_name = config_file_name
        self.template_resource_name = template_resource_name
        self.template_data = template_data

    def exists(self) -> bool:
        return os.path.exists(self.config_file_name)

    async def get_template_file_str(self) -> str:
        if self.template_resource_name is None:
            return None

        with (
            resources.files('langbot.templates').joinpath(self.template_resource_name).open('r', encoding='utf-8') as f
        ):
            return f.read()

    async def create(self):
        if await self.get_template_file_str() is not None:
            with open(self.config_file_name, 'w', encoding='utf-8') as f:
                f.write(await self.get_template_file_str())
        elif self.template_data is not None:
            with open(self.config_file_name, 'w', encoding='utf-8') as f:
                json.dump(self.template_data, f, indent=4, ensure_ascii=False)
        else:
            raise ValueError('template_file_name or template_data must be provided')

    async def load(self, completion: bool = True) -> dict:
        if not self.exists():
            await self.create()

        template_file_str = await self.get_template_file_str()

        if template_file_str is not None:
            self.template_data = json.loads(template_file_str)

        with open(self.config_file_name, 'r', encoding='utf-8') as f:
            try:
                cfg = json.load(f)
            except json.JSONDecodeError as e:
                raise Exception(f'Syntax error in config file {self.config_file_name}: {e}')

        if completion:
            for key in self.template_data:
                if key not in cfg:
                    cfg[key] = self.template_data[key]

        return cfg

    async def save(self, cfg: dict):
        with open(self.config_file_name, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def save_sync(self, cfg: dict):
        with open(self.config_file_name, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
