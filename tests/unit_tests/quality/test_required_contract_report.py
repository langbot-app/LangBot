"""The optional-dependency CI guard must reject a false-green JUnit report."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'assert-required-tests.py'
SPEC = importlib.util.spec_from_file_location('required_contract_report', SCRIPT)
assert SPEC is not None and SPEC.loader is not None
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


def write_report(tmp_path, cases):
    path = tmp_path / 'report.xml'
    path.write_text(f'<testsuites><testsuite>{cases}</testsuite></testsuites>')
    return path


def test_accepts_exact_passing_cases(tmp_path):
    path = write_report(
        tmp_path, '<testcase classname="contracts" name="first"/><testcase classname="contracts" name="second"/>'
    )
    assert REPORT.verify_report(path, 'contracts', 2) == 2


@pytest.mark.parametrize('outcome', ['skipped', 'failure', 'error'])
def test_rejects_every_nonpassing_outcome(tmp_path, outcome):
    path = write_report(tmp_path, f'<testcase classname="contracts" name="required"><{outcome}/></testcase>')
    with pytest.raises(ValueError, match=outcome):
        REPORT.verify_report(path, 'contracts', 1)


@pytest.mark.parametrize('count', [0, 2])
def test_rejects_changed_case_count(tmp_path, count):
    path = write_report(tmp_path, '<testcase classname="contracts" name="case"/>' * count)
    with pytest.raises(ValueError, match='Expected 1 tests'):
        REPORT.verify_report(path, 'contracts', 1)


def test_rejects_wrong_module(tmp_path):
    path = write_report(tmp_path, '<testcase classname="unrelated" name="case"/>')
    with pytest.raises(ValueError, match='Unexpected test module'):
        REPORT.verify_report(path, 'contracts', 1)


def test_rejects_missing_report(tmp_path):
    with pytest.raises(FileNotFoundError):
        REPORT.verify_report(tmp_path / 'missing.xml', 'contracts', 1)


def test_command_line_success_and_failure(tmp_path):
    path = write_report(tmp_path, '<testcase classname="contracts" name="case"/>')
    command = [sys.executable, str(SCRIPT), str(path), '--module', 'contracts', '--expected-tests']
    good = subprocess.run([*command, '1'], capture_output=True, text=True)
    assert good.returncode == 0
    assert '1 required tests passed, 0 skipped' in good.stdout
    bad = subprocess.run([*command, '0'], capture_output=True, text=True)
    assert bad.returncode != 0
    assert 'must be positive' in bad.stderr


def test_rejects_wrong_function(tmp_path):
    path = write_report(tmp_path, '<testcase classname="contracts" name="unrelated"/>')
    with pytest.raises(ValueError, match='Unexpected test name'):
        REPORT.verify_report(path, 'contracts', 1, 'test_required')
