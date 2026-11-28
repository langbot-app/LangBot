"""Self-tests for the 27-module static dependency graph gate."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from textwrap import dedent
import unittest


SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
GATE = SCRIPTS_DIR / 'check_module_graph.py'
GRAPH_FILE = SCRIPTS_DIR / 'module_graph.json'


class ModuleGraphGateTests(unittest.TestCase):
    def _write_graph(self, root: Path, modules: dict) -> Path:
        graph_path = root / 'graph.json'
        graph_path.write_text(
            json.dumps(
                {
                    'schema_version': 1,
                    'layers': ['foundation', 'infrastructure', 'domain'],
                    'modules': modules,
                }
            ),
            encoding='utf-8',
        )
        return graph_path

    def _run(self, root: Path, graph_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GATE), '--root', str(root), '--graph', str(graph_path), *extra],
            capture_output=True,
            text=True,
        )

    def test_blocks_undeclared_edges_and_allows_type_checking_imports(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mod in ('config', 'persistence', 'pipeline'):
                (root / f'src/langbot/pkg/{mod}').mkdir(parents=True)
            graph = self._write_graph(
                root,
                {
                    'config': {'layer': 'foundation', 'depends_on': []},
                    'persistence': {'layer': 'infrastructure', 'depends_on': ['config']},
                    'pipeline': {'layer': 'domain', 'depends_on': ['persistence']},
                },
            )
            # TYPE_CHECKING-only upward import is permitted.
            (root / 'src/langbot/pkg/config/sample.py').write_text(
                dedent("""\
                    import typing
                    if typing.TYPE_CHECKING:
                        from ..pipeline import runner
                """),
                encoding='utf-8',
            )
            self.assertEqual(self._run(root, graph).returncode, 0)

            # Runtime import violating depends_on must fail with guidance.
            (root / 'src/langbot/pkg/config/sample.py').write_text(
                'from ..pipeline import runner\n',
                encoding='utf-8',
            )
            bad = self._run(root, graph)
            self.assertEqual(bad.returncode, 1)
            self.assertIn('FORBIDDEN_MODULE_EDGE', bad.stdout)
            self.assertIn('langbot.pkg.config', bad.stdout)
            self.assertIn('langbot.pkg.pipeline', bad.stdout)

    def test_enforces_private_submodules_hide_internals(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mod in ('persistence', 'pipeline'):
                (root / f'src/langbot/pkg/{mod}').mkdir(parents=True)
            graph = self._write_graph(
                root,
                {
                    'persistence': {
                        'layer': 'infrastructure',
                        'depends_on': [],
                        'private_submodules': ['databases', 'migrations'],
                    },
                    'pipeline': {'layer': 'domain', 'depends_on': ['persistence']},
                },
            )
            # Public persistence import is allowed.
            (root / 'src/langbot/pkg/pipeline/good.py').write_text(
                'from langbot.pkg.persistence import tenant_uow\n',
                encoding='utf-8',
            )
            self.assertEqual(self._run(root, graph).returncode, 0)

            # Importing a private submodule fails even though persistence is in depends_on.
            (root / 'src/langbot/pkg/pipeline/bad.py').write_text(
                'from ..persistence.databases import sqlite\n',
                encoding='utf-8',
            )
            bad = self._run(root, graph)
            self.assertEqual(bad.returncode, 1)
            self.assertIn('PRIVATE_SUBMODULE_IMPORT', bad.stdout)
            self.assertIn('langbot.pkg.persistence.databases', bad.stdout)

    def test_rejects_unregistered_new_package_and_supports_strict_and_mermaid(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mod in ('config', 'unregistered_pkg'):
                (root / f'src/langbot/pkg/{mod}').mkdir(parents=True)
            graph = self._write_graph(
                root,
                {'config': {'layer': 'foundation', 'depends_on': []}},
            )
            bad = self._run(root, graph)
            self.assertEqual(bad.returncode, 1)
            self.assertIn('UNREGISTERED_MODULE', bad.stdout)

            # Mermaid output renders cleanly.
            mermaid = self._run(root, graph, '--mermaid')
            self.assertEqual(mermaid.returncode, 0)
            self.assertIn('flowchart LR', mermaid.stdout)

    def test_repo_module_graph_passes(self):
        res = self._run(REPO_ROOT, GRAPH_FILE)
        self.assertEqual(res.returncode, 0, (res.stdout, res.stderr))


if __name__ == '__main__':
    unittest.main(verbosity=2)
