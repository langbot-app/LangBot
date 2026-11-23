"""Exercise the required-suite policy through real pytest collection and execution."""

from pathlib import Path
import os
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
PASSING = """
import pytest

@pytest.mark.security
@pytest.mark.contract('debug_exec_absent')
@pytest.mark.parametrize('value', [1, 2, 3])
def test_renamed_behavior(value):
    assert value > 0

@pytest.mark.security
@pytest.mark.contract('debug_route_absent')
def test_another_name():
    pass

def test_unrelated():
    assert False
"""


def run_suite(tmp_path, source, *args):
    (tmp_path / 'moved').mkdir(exist_ok=True)
    (tmp_path / 'moved/test_any_name.py').write_text(source)
    (tmp_path / 'pytest.ini').write_text('[pytest]\nmarkers =\n    security: suite\n    contract(name): behavior\n')
    return subprocess.run(
        [
            sys.executable,
            '-m',
            'pytest',
            '-p',
            'tests.utils.required_suites',
            '--required-suite',
            'security',
            '-q',
            *args,
        ],
        cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(ROOT)},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_renames_moves_and_parameter_growth_need_no_ci_edit(tmp_path):
    result = run_suite(tmp_path, PASSING)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '4 passed, 1 deselected' in result.stdout
    result = run_suite(tmp_path, PASSING.replace('[1, 2, 3]', '[1, 2, 3, 4]'))
    assert result.returncode == 0, result.stdout + result.stderr
    assert '5 passed, 1 deselected' in result.stdout


@pytest.mark.parametrize(
    'statement',
    [
        "pytest.skip('dependency unavailable')",
        "pytest.xfail('known bug')",
        'assert False',
        "raise RuntimeError('broken')",
    ],
)
def test_required_cases_must_actually_pass(tmp_path, statement):
    result = run_suite(tmp_path, PASSING.replace('    pass', f'    {statement}'))
    assert result.returncode != 0
    assert 'all selected cases must pass' in result.stdout


def test_unexpected_xpass_is_not_a_required_pass(tmp_path):
    source = PASSING.replace('def test_another_name():', '@pytest.mark.xfail(strict=False)\ndef test_another_name():')
    result = run_suite(tmp_path, source)
    assert result.returncode != 0
    assert 'all selected cases must pass' in result.stdout


def test_missing_behavior_cannot_be_replaced_by_more_unrelated_cases(tmp_path):
    source = PASSING.replace("@pytest.mark.contract('debug_route_absent')", '')
    result = run_suite(tmp_path, source)
    assert result.returncode != 0
    assert "missing contracts: ['debug_route_absent']" in result.stderr


def test_empty_suite_fails(tmp_path):
    result = run_suite(tmp_path, 'def test_unrelated(): pass')
    assert result.returncode != 0
    assert 'missing contracts' in result.stderr


@pytest.mark.parametrize('args', [('-k', 'renamed'), ('-m', 'security'), ('--deselect', 'moved/test_any_name.py')])
def test_required_suite_rejects_partial_filters(tmp_path, args):
    result = run_suite(tmp_path, PASSING, *args)
    assert result.returncode != 0
    assert 'cannot be combined' in result.stderr


@pytest.mark.parametrize('phase', ['setup', 'teardown'])
def test_fixture_skips_also_fail(tmp_path, phase):
    fixture = '\n@pytest.fixture(autouse=True)\ndef dependency():\n'
    if phase == 'teardown':
        fixture += '    yield\n'
    fixture += "    pytest.skip('dependency unavailable')\n"
    result = run_suite(tmp_path, PASSING + fixture)
    assert result.returncode != 0
    assert 'all selected cases must pass' in result.stdout


def test_optional_local_execution_still_allows_skips(tmp_path):
    (tmp_path / 'test_optional.py').write_text("import pytest\ndef test_optional(): pytest.skip('no database')")
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-p', 'tests.utils.required_suites', '-q'],
        cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(ROOT)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 skipped' in result.stdout
