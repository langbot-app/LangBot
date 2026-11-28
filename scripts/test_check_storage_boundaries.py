"""Self-tests for the static storage abstraction and layer boundary gate."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from textwrap import dedent
import tomllib
import unittest


SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
GATE = SCRIPTS_DIR / 'check_storage_boundaries.py'
BASELINE_FILE = SCRIPTS_DIR / 'storage_boundaries_baseline.json'

sys.path.insert(0, str(SCRIPTS_DIR))
import check_storage_boundaries as gate  # noqa: E402


class StorageBoundaryRulesTests(unittest.TestCase):
    def test_rejects_storage_dialect_and_driver_imports_outside_persistence(self):
        src = dedent("""\
            import sqlite3
            from sqlalchemy.dialects import postgresql, sqlite
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        """)
        violations = gate.scan_file('src/langbot/pkg/pipeline/sample.py', src)
        rules = [(v.line, v.rule) for v in violations]
        self.assertEqual(
            rules,
            [
                (1, 'STORAGE_DIALECT_IMPORT'),
                (2, 'STORAGE_DIALECT_IMPORT'),
                (2, 'STORAGE_DIALECT_IMPORT'),
                (3, 'STORAGE_DIALECT_IMPORT'),
            ],
        )
        self.assertTrue(all('langbot.pkg.persistence' in v.guidance for v in violations))

    def test_allows_storage_imports_inside_persistence_and_pgvector(self):
        src = dedent("""\
            import sqlite3
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            name = engine.dialect.name
            sql = 'SELECT * FROM sqlite_master'
            conn = ap.persistence_mgr.get_db_engine().connect()
        """)
        self.assertEqual(gate.scan_file('src/langbot/pkg/persistence/dialect.py', src), [])
        self.assertEqual(gate.scan_file('src/langbot/pkg/vector/vdbs/pgvector_db.py', src), [])

    def test_rejects_dialect_name_raw_sql_and_engine_bypass(self):
        src = dedent("""\
            def check(ap, engine):
                if engine.dialect.name == 'sqlite':
                    q1 = 'SELECT name FROM sqlite_master WHERE type="table"'
                    q2 = "SELECT set_config('langbot.workspace_uuid', :w, true)"
                    q3 = 'PRAGMA busy_timeout=5000'
                    return ap.persistence_mgr.get_db_engine().connect()
        """)
        violations = gate.scan_file('src/langbot/pkg/command/sample.py', src)
        self.assertEqual(
            [v.rule for v in violations],
            [
                'DIALECT_NAME_BRANCH',
                'RAW_DIALECT_SQL',
                'RAW_DIALECT_SQL',
                'RAW_DIALECT_SQL',
                'RAW_ENGINE_BYPASS',
            ],
        )

    def test_rejects_controller_and_orchestrator_layer_leaks_including_relative_imports(self):
        ctrl_src = dedent("""\
            from sqlalchemy.exc import IntegrityError
            from .....persistence.write_admission import write_slot
        """)
        ctrl_violations = gate.scan_file('src/langbot/pkg/api/http/controller/groups/sample.py', ctrl_src)
        self.assertEqual([v.rule for v in ctrl_violations], ['LAYER_IMPORT_VIOLATION', 'LAYER_IMPORT_VIOLATION'])

        orch_src = dedent("""\
            from ...persistence.write_admission import sqlite_write_deadline
        """)
        orch_violations = gate.scan_file('src/langbot/pkg/agent/runner/orchestrator.py', orch_src)
        self.assertEqual([v.rule for v in orch_violations], ['LAYER_IMPORT_VIOLATION'])

    def test_persistence_upward_import_blocked_at_runtime_but_allowed_under_type_checking(self):
        src = dedent("""\
            import typing
            from ..core import app as runtime_app

            if typing.TYPE_CHECKING:
                from ..core import app as typed_app
                from ..api.http import context as typed_ctx
        """)
        violations = gate.scan_file('src/langbot/pkg/persistence/sample.py', src)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].line, 2)
        self.assertEqual(violations[0].rule, 'LAYER_IMPORT_VIOLATION')

        # Frozen historical alembic migrations are exempted.
        mig_src = 'from langbot.pkg.command.processor import COMMAND_PROCESSOR_KIND\n'
        self.assertEqual(gate.scan_file('src/langbot/pkg/persistence/alembic/versions/0060_test.py', mig_src), [])

    def test_ratchet_blocks_new_violations_and_handles_tightening(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'src/langbot/pkg/box/legacy.py'
            target.parent.mkdir(parents=True)
            target.write_text('x = engine.dialect.name\n', encoding='utf-8')
            baseline = root / 'baseline.json'

            # Generate baseline -> passes both default and strict.
            res = subprocess.run(
                [sys.executable, str(GATE), '--root', str(root), '--baseline', str(baseline), '--update-baseline'],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn('1 tracked legacy violations', res.stdout)

            for extra in ([], ['--strict-baseline']):
                ok = subprocess.run(
                    [sys.executable, str(GATE), '--root', str(root), '--baseline', str(baseline), *extra],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(ok.returncode, 0, (ok.stdout, ok.stderr))

            # Adding a second violation in the same legacy file must fail immediately.
            target.write_text('x = engine.dialect.name\ny = other.dialect.name\n', encoding='utf-8')
            bad = subprocess.run(
                [sys.executable, str(GATE), '--root', str(root), '--baseline', str(baseline)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(bad.returncode, 1)
            self.assertIn('DIALECT_NAME_BRANCH', bad.stdout)

            # Removing the legacy violation passes default mode (with tighten hint) and fails --strict-baseline.
            target.write_text('x = "clean"\n', encoding='utf-8')
            soft = subprocess.run(
                [sys.executable, str(GATE), '--root', str(root), '--baseline', str(baseline)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(soft.returncode, 0, (soft.stdout, soft.stderr))
            self.assertIn('baseline can be tightened', soft.stdout)

            strict = subprocess.run(
                [sys.executable, str(GATE), '--root', str(root), '--baseline', str(baseline), '--strict-baseline'],
                capture_output=True,
                text=True,
            )
            self.assertEqual(strict.returncode, 1)
            self.assertIn('strict baseline', strict.stdout)

    def test_repo_baseline_is_valid_and_synced_with_ruff_per_file_ignores(self):
        # Default mode enforces zero regressions without blocking cleanup PRs that remove legacy debt.
        res = subprocess.run(
            [sys.executable, str(GATE), '--root', str(REPO_ROOT), '--baseline', str(BASELINE_FILE)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, (res.stdout, res.stderr))

        # Verify pyproject.toml legacy TID251 ignores match STORAGE_DIALECT_IMPORT baseline entries.
        pyproject = tomllib.loads((REPO_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        per_file = pyproject['tool']['ruff']['lint']['per-file-ignores']
        permanent = {
            'src/langbot/pkg/persistence/**',
            'src/langbot/pkg/vector/vdbs/pgvector_db.py',
            'tests/**',
            'tools/**',
            'scripts/**',
        }
        ruff_legacy = {path for path, codes in per_file.items() if 'TID251' in codes and path not in permanent}
        baseline = json.loads(BASELINE_FILE.read_text(encoding='utf-8'))
        ast_legacy = {path for path, rules in baseline.items() if 'STORAGE_DIALECT_IMPORT' in rules}
        self.assertEqual(ruff_legacy, ast_legacy)


if __name__ == '__main__':
    unittest.main(verbosity=2)
