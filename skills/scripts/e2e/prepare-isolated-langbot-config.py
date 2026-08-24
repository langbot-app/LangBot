#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.utils.config_factory import (  # noqa: E402
    create_minimal_config,
    create_test_directories,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--instance-root', required=True, type=Path)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--plugin-debug-port', required=True, type=int)
    args = parser.parse_args()

    config_path = create_minimal_config(args.instance_root, port=args.port)
    create_test_directories(args.instance_root)

    with config_path.open('r', encoding='utf-8') as file:
        config = yaml.safe_load(file)

    config['plugin']['enable'] = True
    config['plugin']['enable_marketplace'] = True
    config['plugin']['display_plugin_debug_url'] = (
        f'ws://127.0.0.1:{args.plugin_debug_port}/plugin/debug/ws'
    )

    with config_path.open('w', encoding='utf-8') as file:
        yaml.safe_dump(config, file, allow_unicode=True, sort_keys=False)


if __name__ == '__main__':
    main()
