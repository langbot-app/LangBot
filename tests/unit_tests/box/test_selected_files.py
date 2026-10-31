import hashlib
import json
import subprocess
import sys

import pytest
from langbot.pkg.box.selected_files import selected_files_script


def run(paths, cleanup=None, limit=100):
    return subprocess.run(
        [
            sys.executable,
            '-c',
            selected_files_script(list(map(str, paths)), max_file_bytes=limit, max_total_bytes=limit, cleanup=cleanup),
        ],
        capture_output=True,
        text=True,
    )


def test_selected_read_and_cleanup(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.write_bytes(b'hello')
    b.write_bytes(b'keep')
    result = run([a])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [{'name': str(a), 'b64': 'aGVsbG8='}]
    assert a.exists() and b.exists()
    assert run([a], {str(a): hashlib.sha256(b'hello').hexdigest()}).returncode == 0
    assert not a.exists() and b.read_bytes() == b'keep'


@pytest.mark.parametrize('bad', ['missing', 'symlink', 'directory', 'size', 'fifo'])
def test_failed_batch_retains_all(tmp_path, bad):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.write_bytes(b'hello')
    if bad == 'symlink':
        b.symlink_to(a)
    elif bad == 'directory':
        b.mkdir()
    elif bad == 'size':
        b.write_bytes(b'x' * 101)
    elif bad == 'fifo':
        import os

        os.mkfifo(b)
    result = run([a, b])
    assert result.returncode != 0
    assert a.read_bytes() == b'hello'


def test_changed_file_is_retained(tmp_path):
    a = tmp_path / 'a'
    a.write_bytes(b'changed')
    assert run([a], {str(a): hashlib.sha256(b'old').hexdigest()}).returncode != 0
    assert a.read_bytes() == b'changed'
