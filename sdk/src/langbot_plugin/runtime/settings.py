from pydantic import Field
from pydantic_settings import BaseSettings


class RuntimeSettings(BaseSettings):
    """Runtime settings using Pydantic Settings"""

    cloud_service_url: str = Field(default="https://space.langbot.app")

    plugin_debug_key: str = Field(default="")

    model_config = {
        "env_file": "data/.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Global settings instance
settings: RuntimeSettings = RuntimeSettings()
