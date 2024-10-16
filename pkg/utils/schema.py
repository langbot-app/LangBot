import os
import json


def load_schema(schema_path: str) -> dict:
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


CONFIG_SYSTEM_SCHEMA = load_schema("templates/schema/system.json")
CONFIG_PIPELINE_SCHEMA = load_schema("templates/schema/pipeline.json")
CONFIG_COMMAND_SCHEMA = load_schema("templates/schema/command.json")
CONFIG_PLATFORM_SCHEMA = load_schema("templates/schema/platform.json")
CONFIG_PROVIDER_SCHEMA = load_schema("templates/schema/provider.json")
