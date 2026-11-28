"""Enforce the declarative 27-module runtime dependency graph for src/langbot/pkg/.

Inspired by Tach / architectural fitness functions, this zero-dependency static gate:
1. Requires every top-level package under ``src/langbot/pkg/`` to be explicitly declared in
   ``scripts/module_graph.json``.
2. Rejects any runtime cross-package import (outside ``if TYPE_CHECKING:`` and frozen
   Alembic migrations) that is not permitted in the source module's ``depends_on`` list.
3. Enforces ``private_submodules`` ("Hide internals"): external modules cannot import
   hidden internal subpackages (such as ``langbot.pkg.persistence.databases`` or
   ``langbot.pkg.persistence.migrations``) even when depending on the parent package.
4. Supports ``--strict`` to flag unused declared edges and ``--mermaid`` to export a
   Mermaid architecture graph.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import tokenize


DEFAULT_GRAPH = Path(__file__).with_name('module_graph.json')
EXEMPT_PREFIXES = ('src/langbot/pkg/persistence/alembic/versions/',)


@dataclass(frozen=True)
class GraphViolation:
    path: str
    line: int
    code: str
    detail: str
    guidance: str

    def format(self) -> str:
        return f'{self.path}:{self.line}: {self.code} {self.detail} -> {self.guidance}'


def load_graph(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('modules'), dict):
        raise ValueError(f'Invalid module graph schema: {path}')
    layers = set(raw.get('layers', []))
    modules = raw['modules']
    for name, spec in modules.items():
        if not isinstance(spec, dict):
            raise ValueError(f'Module {name!r} spec must be an object')
        if layers and spec.get('layer') not in layers:
            raise ValueError(f'Module {name!r} has unknown layer {spec.get("layer")!r}')
        for dep in spec.get('depends_on', []):
            if dep == name:
                raise ValueError(f'Module {name!r} must not list itself in depends_on')
            if dep not in modules:
                raise ValueError(f'Module {name!r} depends_on unknown module {dep!r}')
    return raw


def discover_packages(root: Path) -> set[str]:
    pkg_root = root / 'src' / 'langbot' / 'pkg'
    if not pkg_root.exists():
        return set()
    return {entry.name for entry in pkg_root.iterdir() if entry.is_dir() and not entry.name.startswith(('__', '.'))}


def _collect_type_checking_nodes(tree: ast.AST) -> set[int]:
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_tc = (isinstance(test, ast.Name) and test.id == 'TYPE_CHECKING') or (
            isinstance(test, ast.Attribute) and test.attr == 'TYPE_CHECKING'
        )
        if is_tc:
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    guarded.add(id(sub))
    return guarded


def _resolve_import_targets(rel_path: str, node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    module = node.module or ''
    if node.level > 0:
        parts = Path(rel_path).parts
        pkg_parts = list(parts[1:-1]) if parts and parts[0] == 'src' else list(parts[:-1])
        keep = max(0, len(pkg_parts) - (node.level - 1))
        base = pkg_parts[:keep]
        if module:
            base.append(module)
        full_mod = '.'.join(base)
    else:
        full_mod = module
    targets: list[str] = []
    for alias in node.names:
        targets.append(f'{full_mod}.{alias.name}' if full_mod else alias.name)
    return targets or ([full_mod] if full_mod else [])


def check_repo(
    root: Path,
    graph: dict,
) -> tuple[list[GraphViolation], dict[str, set[str]], list[str]]:
    modules = graph['modules']
    actual_pkgs = discover_packages(root)
    declared_pkgs = set(modules.keys())

    violations: list[GraphViolation] = []
    for missing in sorted(actual_pkgs - declared_pkgs):
        violations.append(
            GraphViolation(
                path=f'src/langbot/pkg/{missing}',
                line=1,
                code='UNREGISTERED_MODULE',
                detail=f'top-level package `langbot.pkg.{missing}` is not declared in module_graph.json',
                guidance='declare its layer and allowed `depends_on` in scripts/module_graph.json',
            )
        )
    for ghost in sorted(declared_pkgs - actual_pkgs):
        violations.append(
            GraphViolation(
                path='scripts/module_graph.json',
                line=1,
                code='STALE_DECLARED_MODULE',
                detail=f'declared module `langbot.pkg.{ghost}` does not exist under src/langbot/pkg/',
                guidance='remove obsolete entry from scripts/module_graph.json',
            )
        )

    observed_edges: dict[str, set[str]] = defaultdict(set)
    pkg_root = root / 'src' / 'langbot' / 'pkg'
    if pkg_root.exists():
        for path in sorted(pkg_root.rglob('*.py')):
            if path.is_symlink():
                continue
            rel_path = path.relative_to(root).as_posix()
            if rel_path.startswith(EXEMPT_PREFIXES):
                continue
            parts = Path(rel_path).parts
            if len(parts) < 5:
                continue
            src_mod = parts[3]
            if src_mod not in modules:
                continue
            allowed_deps = set(modules[src_mod].get('depends_on', []))

            with tokenize.open(path) as handle:
                source = handle.read()
            tree = ast.parse(source, filename=rel_path)
            tc_nodes = _collect_type_checking_nodes(tree)

            for node in ast.walk(tree):
                if id(node) in tc_nodes or not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                seen_on_stmt: set[tuple[str, str | None]] = set()
                for target in _resolve_import_targets(rel_path, node):
                    if not target.startswith('langbot.pkg.'):
                        continue
                    segments = target.split('.')
                    if len(segments) < 3:
                        continue
                    tgt_mod = segments[2]
                    if tgt_mod == src_mod or tgt_mod not in modules:
                        continue
                    submod = segments[3] if len(segments) >= 4 else None
                    observed_edges[src_mod].add(tgt_mod)

                    if tgt_mod not in allowed_deps and (tgt_mod, None) not in seen_on_stmt:
                        seen_on_stmt.add((tgt_mod, None))
                        src_layer = modules[src_mod].get('layer', 'unknown')
                        tgt_layer = modules[tgt_mod].get('layer', 'unknown')
                        violations.append(
                            GraphViolation(
                                path=rel_path,
                                line=node.lineno,
                                code='FORBIDDEN_MODULE_EDGE',
                                detail=(
                                    f'`langbot.pkg.{src_mod}` ({src_layer}) must not depend at runtime '
                                    f'on `langbot.pkg.{tgt_mod}` ({tgt_layer}) via `{target}`'
                                ),
                                guidance=(
                                    'keep dependencies aligned with the architecture graph, use '
                                    '`if typing.TYPE_CHECKING:` for type-only imports, or explicitly '
                                    'review and update scripts/module_graph.json'
                                ),
                            )
                        )

                    private_subs = set(modules[tgt_mod].get('private_submodules', []))
                    if submod in private_subs and (tgt_mod, submod) not in seen_on_stmt:
                        seen_on_stmt.add((tgt_mod, submod))
                        violations.append(
                            GraphViolation(
                                path=rel_path,
                                line=node.lineno,
                                code='PRIVATE_SUBMODULE_IMPORT',
                                detail=(
                                    f'`langbot.pkg.{src_mod}` imported hidden internal submodule '
                                    f'`langbot.pkg.{tgt_mod}.{submod}`'
                                ),
                                guidance=f'use public interfaces of `langbot.pkg.{tgt_mod}` instead',
                            )
                        )

    unused_edges: list[str] = []
    for mod, spec in sorted(modules.items()):
        for dep in sorted(spec.get('depends_on', [])):
            if dep not in observed_edges.get(mod, set()):
                unused_edges.append(f'{mod} -> {dep}')

    violations.sort(key=lambda item: (item.path, item.line, item.code, item.detail))
    return violations, observed_edges, unused_edges


def render_mermaid(graph: dict) -> str:
    lines = ['flowchart LR']
    by_layer: dict[str, list[str]] = defaultdict(list)
    for mod, spec in sorted(graph['modules'].items()):
        by_layer[spec['layer']].append(mod)
    for layer in graph.get('layers', sorted(by_layer)):
        mods = by_layer.get(layer, [])
        if not mods:
            continue
        lines.append(f'  subgraph {layer}')
        for mod in mods:
            lines.append(f'    {mod}')
        lines.append('  end')
    for mod, spec in sorted(graph['modules'].items()):
        for dep in sorted(spec.get('depends_on', [])):
            lines.append(f'  {mod} --> {dep}')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Repository root directory')
    parser.add_argument('--graph', type=Path, default=DEFAULT_GRAPH, help='Module graph JSON path')
    parser.add_argument('--strict', action='store_true', help='Also fail on unused declared depends_on edges')
    parser.add_argument('--mermaid', action='store_true', help='Print Mermaid dependency diagram and exit 0')
    args = parser.parse_args(argv)

    graph = load_graph(args.graph)
    if args.mermaid:
        print(render_mermaid(graph))
        return 0

    violations, _, unused_edges = check_repo(args.root.resolve(), graph)
    if violations:
        print('Module dependency graph violations detected:')
        for item in violations:
            print('  ' + item.format())
        return 1

    if args.strict and unused_edges:
        print('Unused declared module dependencies (--strict):')
        for edge in unused_edges:
            print(f'  {edge}')
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
