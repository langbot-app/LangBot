"""Keep complexity reporting honest about metric values and baseline changes."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def reporter():
    path = Path(__file__).resolve().parents[2] / 'scripts/test-complexity.py'
    spec = importlib.util.spec_from_file_location('complexity_report', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source(root, text, name='sample.py'):
    path = root / 'src/langbot' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def commit(root):
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True).stdout.decode().strip()

    git('init', '-q')
    git('add', 'src')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'baseline')
    return git('rev-parse', 'HEAD')


def test_real_ruff_counts_branches_nested_functions_and_ignores_noqa(reporter, tmp_path):
    source(
        tmp_path,
        """\
class Worker:
    def run(self, value):  # noqa: C901
        if value:
            return value
        return None

async def outer(value):
    def inner():
        return 1
    if value:
        return inner()
    return None
""",
    )
    functions = {item['name']: item for item in reporter.measure(tmp_path)}
    assert functions['Worker.run']['complexity'] == 2
    assert functions['outer']['complexity'] == 3  # Ruff also includes the nested definition.
    assert functions['outer.inner']['complexity'] == 1
    assert functions['Worker.run']['path'] == 'src/langbot/sample.py'


def test_all_source_includes_libs_and_overrides_repo_lint_exclusions(reporter, tmp_path):
    source(tmp_path, 'def vendored():\n    pass\n', 'libs/helper.py')
    (tmp_path / 'pyproject.toml').write_text('[tool.ruff]\nexclude = ["src"]\n')
    (tmp_path / '.gitignore').write_text('src/\n')
    assert [item['name'] for item in reporter.measure(tmp_path)] == ['vendored']


def test_invalid_source_is_an_analysis_failure(reporter, tmp_path):
    source(tmp_path, 'def broken(:\n')
    with pytest.raises(ValueError, match='Unexpected Ruff diagnostic'):
        reporter.measure(tmp_path)


def test_duplicate_definitions_have_distinct_stable_occurrences(reporter, tmp_path):
    path = source(
        tmp_path,
        """\
class Worker:
    @property
    def value(self):
        return 1
    @value.setter
    def value(self, value):
        pass
""",
    )
    definitions = list(reporter.index_functions(path).values())
    assert [item['name'] for item in definitions] == ['Worker.value', 'Worker.value']
    assert [item['occurrence'] for item in definitions] == [1, 2]


def test_changed_function_deltas_additions_deletions_and_formatting(reporter, tmp_path):
    path = source(
        tmp_path,
        """\
def changed(value):
    return value

def removed():
    pass

def unchanged():
    return 1
""",
    )
    before = reporter.measure(tmp_path)
    path.write_text("""\
# Moving lines and adding comments does not change a function.
def unchanged():
    return 1

def changed(value):
    if value:
        return value
    return None

def added():
    pass
""")
    changes = reporter.compare(before, reporter.measure(tmp_path), {})
    assert {item['status'] for item in changes} == {'modified', 'added', 'deleted'}
    modified = next(item for item in changes if item['status'] == 'modified')
    assert modified['after']['name'] == 'changed'
    assert modified['delta'] == 1
    assert all(item['delta'] is None for item in changes if item['status'] != 'modified')


def test_function_renames_are_added_deleted_not_false_improvements(reporter, tmp_path):
    path = source(tmp_path, 'def old_name():\n    pass\n')
    before = reporter.measure(tmp_path)
    path.write_text('def new_name():\n    pass\n')
    changes = reporter.compare(before, reporter.measure(tmp_path), {})
    assert {item['status'] for item in changes} == {'added', 'deleted'}
    assert all(item['delta'] is None for item in changes)


def test_git_baseline_and_file_rename_preserve_identity(reporter, tmp_path):
    path = source(tmp_path, 'def sample():\n    return 1\n')
    revision = commit(tmp_path)
    path.rename(path.with_name('renamed.py'))
    # Stage the destination so git can detect its similarity to the deleted file.
    subprocess.run(['git', 'add', 'src'], cwd=tmp_path, check=True)
    resolved, before = reporter.baseline(tmp_path, revision)
    assert resolved == revision
    assert before[0]['path'] == 'src/langbot/sample.py'
    renames = reporter.file_renames(tmp_path, revision)
    assert renames == {'src/langbot/renamed.py': 'src/langbot/sample.py'}
    changes = reporter.compare(before, reporter.measure(tmp_path), renames)
    assert len(changes) == 1
    assert changes[0]['status'] == 'renamed_file'
    assert changes[0]['delta'] == 0


def test_invalid_base_ref_fails_rather_than_using_head(reporter, tmp_path):
    source(tmp_path, 'def sample():\n    pass\n')
    commit(tmp_path)
    with pytest.raises(ValueError):
        reporter.baseline(tmp_path, 'does-not-exist')


def coverage_document(branch=True):
    return {
        'meta': {'branch_coverage': branch},
        'files': {
            'src/langbot/sample.py': {
                'executed_lines': [1, 2, 3],
                'missing_lines': [4],
                'executed_branches': [[2, 3]],
                'missing_branches': [[2, 4]],
                'summary': {
                    'covered_lines': 3,
                    'num_statements': 4,
                    'covered_branches': 1,
                    'num_branches': 2,
                    'percent_covered': 66.666,
                },
            },
            'tests/unrelated.py': {
                'executed_lines': [1],
                'missing_lines': [],
                'summary': {'covered_lines': 1, 'num_statements': 1},
            },
        },
    }


def test_line_and_branch_coverage_are_separate_not_combined(reporter, tmp_path):
    source(tmp_path, 'def sample(value):\n    if value:\n        return 1\n    return 0\n')
    functions = reporter.measure(tmp_path)
    report = reporter.attach_coverage(functions, coverage_document(), tmp_path)
    assert report['line_percent'] == 75
    assert report['branch_percent'] == 50
    assert report['matched_source_files'] == 1
    assert functions[0]['coverage']['line_percent'] == 75
    assert functions[0]['coverage']['branch_percent'] == 50


def test_unknown_coverage_is_not_reported_as_zero(reporter, tmp_path):
    source(tmp_path, 'def unknown():\n    pass\n', 'unknown.py')
    functions = reporter.measure(tmp_path)
    report = reporter.attach_coverage(functions, coverage_document(branch=False), tmp_path)
    assert functions[0]['coverage'] is None
    assert report['functions_without_coverage'] == 1
    assert report['branch_percent'] is None


def test_no_branch_function_has_no_artificial_branch_percent(reporter, tmp_path):
    source(tmp_path, '\n\n\n\ndef sample():\n    return 1\n')
    functions = reporter.measure(tmp_path)
    reporter.attach_coverage(functions, coverage_document(), tmp_path)
    assert functions[0]['coverage']['branch_percent'] is None
    assert functions[0]['coverage']['line_percent'] is None


def test_empty_scope_statistics_have_no_artificial_averages(reporter):
    stats = reporter.statistics([])
    assert stats['function_count'] == 0
    assert stats['maximum'] is None
    assert stats['mean'] is None
    assert sum(stats['distribution'].values()) == 0


def test_cli_writes_reports_and_high_complexity_is_not_failure(reporter, tmp_path):
    # 60 independent decisions produce CC 61, intentionally above ordinary limits.
    source(tmp_path, 'def high(value):\n' + '    if value:\n        value -= 1\n' * 60)
    json_path = tmp_path / 'reports/complexity.json'
    summary_path = tmp_path / 'reports/complexity.md'
    assert reporter.main(['--root', str(tmp_path), '--json', str(json_path), '--summary', str(summary_path)]) == 0
    document = json.loads(json_path.read_text())
    assert document['current']['maximum'] == 61
    assert document['current']['distribution']['51+'] == 1
    assert 'CC=61' in summary_path.read_text()
    assert 'report only; no complexity gate' in summary_path.read_text()


def test_missing_source_fails_without_publishing_misleading_empty_report(reporter, tmp_path):
    destination = tmp_path / 'complexity.json'
    assert reporter.main(['--root', str(tmp_path), '--json', str(destination)]) == 1
    assert not destination.exists()


def test_notebooks_and_stubs_are_outside_python_source_scope(reporter, tmp_path):
    source(tmp_path, 'def sample():\n    pass\n')
    source(tmp_path, 'def annotation_only(): ...\n', 'types.pyi')
    source(tmp_path, 'invalid notebook content', 'notebook.ipynb')
    assert [item['name'] for item in reporter.measure(tmp_path)] == ['sample']


def test_excluded_executed_lines_do_not_inflate_function_coverage(reporter, tmp_path):
    source(tmp_path, 'def sample(value):\n    if value:\n        return 1\n    return 0\n')
    document = coverage_document()
    document['files']['src/langbot/sample.py']['excluded_lines'] = [3]
    functions = reporter.measure(tmp_path)
    reporter.attach_coverage(functions, document, tmp_path)
    assert functions[0]['coverage']['line_percent'] == 66.67
