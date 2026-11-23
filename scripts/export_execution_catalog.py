"""Export ExecutionAPI catalog snapshot as JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from langbot.pkg.api.application.execution import ExecutionAPI


def export_catalog(output_path: Path) -> list[dict]:
    api = ExecutionAPI(None)
    catalog = api.catalog()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write('\n')
    return catalog


if __name__ == '__main__':
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('execution_api_catalog.json')
    catalog = export_catalog(destination)
    print(f'Exported {len(catalog)} operations to {destination}')
