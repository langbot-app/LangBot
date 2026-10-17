"""Bounded live model probe; credentials enter via hidden terminal input only."""

import getpass
import os
from pathlib import Path
import subprocess
import sys
import httpx

base_url = os.environ['LANG16_LLM_BASE_URL'].rstrip('/')
key = getpass.getpass('Test API key (hidden): ')
with httpx.Client(timeout=20) as client:
    response = client.get(base_url + '/models', headers={'Authorization': 'Bearer ' + key})
    if response.status_code != 200:
        raise SystemExit('Model listing HTTP ' + str(response.status_code))
    names = {m['id'] for m in response.json()['data']}
selected = next((m for m in ('deepseek-chat', 'gpt-4o-mini', 'gpt-4.1-mini', 'gpt-4.1-nano') if m in names), None)
if not selected:
    print('Available model IDs:', ', '.join(sorted(names)), flush=True)
    raise SystemExit('No eligible small test model available')
print('Selected test model:', selected, flush=True)
env = dict(
    os.environ,
    LANG16_LLM_KEY=key,
    LANG16_LLM_MODEL=selected,
    LANG16_ONEBOT='1',
    LANG16_RUNNER='1',
    LANG16_BOX='1',
    LANG16_SECONDS='120',
)
raise SystemExit(subprocess.call([sys.executable, str(Path(__file__).with_name('lang16_baseline.py'))], env=env))
