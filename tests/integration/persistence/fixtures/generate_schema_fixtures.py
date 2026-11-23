"""Reproduce immutable historical ORM DDL snapshots without a database."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types

import sqlalchemy as sa

from langbot.pkg.utils import constants


ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
SOURCE = 'src/langbot/pkg/entity/persistence/'
REFS = {
    'baseline': ('9cd3544d59600fcb88700d05e4b211f59ac00445', '0001_baseline'),
    'master': ('9b7ba0d64708496ace30a82866f6dbc185f089dc', '0024_passkey_credentials'),
    'beta': ('03854b5d33d8b66fec4c86a77714e0e7512a31bd', '0025_bot_plugin_processors'),
}


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True)


def generate() -> None:
    # Only the baseline module's initial_metadata seed list reads this removed
    # constant. It does not affect any table, column, constraint or generated DDL.
    constants.required_database_version = 25
    for name, (commit, revision) in REFS.items():
        paths = git('ls-tree', '-r', '--name-only', commit, SOURCE).splitlines()
        with tempfile.TemporaryDirectory(prefix='langbot-historical-schema-') as directory:
            package = Path(directory)
            for path in paths:
                if path.endswith('.py'):
                    (package / Path(path).name).write_text(git('show', f'{commit}:{path}'))
            # Keep ...utils imports working but give each snapshot its own Base.
            package_name = f'langbot.pkg.entity.historical_{name}'
            module = types.ModuleType(package_name)
            module.__path__ = [directory]
            sys.modules[package_name] = module
            for path in sorted(package.glob('*.py')):
                importlib.import_module(f'{package_name}.{path.stem}')
            metadata = importlib.import_module(f'{package_name}.base').Base.metadata
            dialects = {}
            for dialect in ('sqlite', 'postgresql'):
                statements = []
                engine = sa.create_mock_engine(
                    f'{dialect}://',
                    lambda sql, *args, **kwargs: statements.append(str(sql.compile(dialect=engine.dialect)).strip()),
                )
                metadata.create_all(engine)
                dialects[dialect] = statements
            payload = {'source_commit': commit, 'source_path': SOURCE, 'revision': revision, 'dialects': dialects}
            (OUTPUT / f'{name}_schema.json').write_text(json.dumps(payload, indent=2) + '\n')
            print(f'{name}: {commit}, {len(metadata.tables)} historical ORM tables')


if __name__ == '__main__':
    generate()
