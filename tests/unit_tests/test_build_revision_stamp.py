"""Release artifacts must identify their actual source, not a branch label."""

import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('stamp_build_revision', ROOT / 'scripts/stamp_build_revision.py')
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_stamp_accepts_full_revision(tmp_path):
    target = tmp_path / 'src/langbot/_build_info.py'
    target.parent.mkdir(parents=True)
    revision = 'a1' * 20
    assert MODULE.stamp(tmp_path, revision) == revision
    assignments = [node for node in ast.parse(target.read_text()).body if isinstance(node, ast.Assign)]
    assert len(assignments) == 1
    assert ast.literal_eval(assignments[0].value) == revision


@pytest.mark.parametrize('revision', ['main', 'abc123', 'A' * 40, 'a' * 39, 'a' * 41, '../secret', 'a' * 40 + '\n'])
def test_stamp_rejects_non_revision_before_write(tmp_path, revision):
    with pytest.raises(ValueError):
        MODULE.stamp(tmp_path, revision)
    assert not (tmp_path / 'src').exists()
