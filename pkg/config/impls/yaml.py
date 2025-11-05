import os
import shutil
import yaml
from typing import Any

from .. import model as file_model


def _apply_env_overrides(cfg: dict) -> dict:
    """Apply environment variable overrides to config
    
    Environment variables should be uppercase and use __ (double underscore) 
    to represent nested keys. For example:
    - CONCURRENCY__PIPELINE overrides concurrency.pipeline
    - PLUGIN__RUNTIME_WS_URL overrides plugin.runtime_ws_url
    
    Arrays and dict types are ignored.
    
    Args:
        cfg: Configuration dictionary
        
    Returns:
        Updated configuration dictionary
    """
    def set_nested_value(data: dict, keys: list[str], value: Any) -> bool:
        """Set a nested value in a dictionary
        
        Args:
            data: Dictionary to modify
            keys: List of keys representing the path
            value: Value to set
            
        Returns:
            True if value was set, False if path doesn't exist or is invalid type
        """
        if not keys:
            return False
            
        # Navigate to the parent of the target key
        current = data
        for key in keys[:-1]:
            if key not in current:
                return False
            if not isinstance(current[key], dict):
                return False
            current = current[key]
        
        # Check if final key exists and is not a dict or list
        final_key = keys[-1]
        if final_key not in current:
            return False
        if isinstance(current[final_key], (dict, list)):
            return False
            
        # Set the value
        current[final_key] = value
        return True
    
    def convert_value(value: str, original_value: Any) -> Any:
        """Convert string value to appropriate type based on original value
        
        Args:
            value: String value from environment variable
            original_value: Original value to infer type from
            
        Returns:
            Converted value
        """
        if isinstance(original_value, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(original_value, int):
            try:
                return int(value)
            except ValueError:
                return value
        elif isinstance(original_value, float):
            try:
                return float(value)
            except ValueError:
                return value
        else:
            return value
    
    # Process environment variables
    for env_key, env_value in os.environ.items():
        # Check if the environment variable is uppercase and contains __
        if not env_key.isupper():
            continue
        if '__' not in env_key:
            continue
            
        # Convert environment variable name to config path
        # e.g., CONCURRENCY__PIPELINE -> ['concurrency', 'pipeline']
        keys = [key.lower() for key in env_key.split('__')]
        
        # Get the original value to determine type
        current = cfg
        original_value = None
        valid_path = True
        
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                valid_path = False
                break
            if key == keys[-1]:
                original_value = current[key]
            else:
                current = current[key]
        
        if not valid_path or original_value is None:
            continue
            
        # Skip if the value is a dict or list
        if isinstance(original_value, (dict, list)):
            continue
        
        # Convert and set the value
        converted_value = convert_value(env_value, original_value)
        set_nested_value(cfg, keys, converted_value)
    
    return cfg


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
        
        # Apply environment variable overrides
        cfg = _apply_env_overrides(cfg)

        return cfg

    async def save(self, cfg: dict):
        with open(self.config_file_name, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, indent=4, allow_unicode=True)

    def save_sync(self, cfg: dict):
        with open(self.config_file_name, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, indent=4, allow_unicode=True)
