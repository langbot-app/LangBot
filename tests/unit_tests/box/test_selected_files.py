import hashlib
import json
import subprocess
import sys
import uuid

import pytest
from langbot.pkg.box.selected_files import selected_files_cleanup_script, selected_files_script


def run(paths, cleanup=None, limit=100, snapshot_root=None):
    return subprocess.run(
        [
            sys.executable,
            '-c',
            selected_files_script(
                list(map(str, paths)),
                max_file_bytes=limit,
                max_total_bytes=limit,
                cleanup=cleanup,
                snapshot_root=str(snapshot_root) if snapshot_root is not None else None,
            ),
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


def cleanup_snapshot(root):
    return subprocess.run(
        [sys.executable, '-c', selected_files_cleanup_script(str(root))],
        capture_output=True,
        text=True,
    )


def test_selected_snapshot_preserves_source_and_returns_metadata(tmp_path):
    source = tmp_path / 'source.pdf'
    content = b'%PDF-1.7\n' + bytes(range(256)) * 2048
    source.write_bytes(content)
    root = tmp_path / 'new-workspace' / ('.langbot-export-' + uuid.uuid4().hex)
    result = run([source], limit=len(content), snapshot_root=root)
    assert result.returncode == 0, result.stderr
    entries = json.loads(result.stdout)
    assert len(entries) == 1
    item = entries[0]
    assert set(item) == {'index', 'name', 'snapshot_path', 'size', 'sha256'}
    assert item['index'] == 0
    assert item['name'] == str(source)
    assert item['size'] == len(content)
    assert item['sha256'] == hashlib.sha256(content).hexdigest()
    assert len(result.stdout) < 1024
    from pathlib import Path

    snapshot = Path(item['snapshot_path'])
    assert snapshot.parent == root
    assert snapshot.read_bytes() == content
    source.write_bytes(b'changed after snapshot')
    assert snapshot.read_bytes() == content
    cleaned = cleanup_snapshot(root)
    assert cleaned.returncode == 0, cleaned.stderr
    assert not root.exists()
    assert cleanup_snapshot(root).returncode == 0
    assert source.read_bytes() == b'changed after snapshot'


@pytest.mark.parametrize('bad', ['missing', 'symlink', 'size'])
def test_failed_snapshot_batch_cleans_staging_and_retains_sources(tmp_path, bad):
    source, other = tmp_path / 'source', tmp_path / 'other'
    source.write_bytes(b'original')
    if bad == 'symlink':
        other.symlink_to(source)
    elif bad == 'size':
        other.write_bytes(b'x' * 101)
    root = tmp_path / ('.langbot-export-' + uuid.uuid4().hex)
    result = run([source, other], snapshot_root=root)
    assert result.returncode != 0
    assert not root.exists()
    assert source.read_bytes() == b'original'


def test_snapshot_cleanup_retains_unknown_files_and_known_snapshot(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'original')
    root = tmp_path / ('.langbot-export-' + uuid.uuid4().hex)
    result = run([source], snapshot_root=root)
    assert result.returncode == 0, result.stderr
    snapshot_name = json.loads(result.stdout)[0]['snapshot_path'].rsplit('/', 1)[-1]
    unknown = root / 'unrelated'
    unknown.write_bytes(b'keep')
    cleaned = cleanup_snapshot(root)
    assert cleaned.returncode != 0
    assert unknown.read_bytes() == b'keep'
    assert (root / snapshot_name).read_bytes() == b'original'
    unknown.unlink()
    assert cleanup_snapshot(root).returncode == 0


def test_snapshot_rejects_linked_parent_and_preexisting_root(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'original')
    directory = tmp_path / 'workspace'
    directory.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(directory, target_is_directory=True)
    root = alias / ('.langbot-export-' + uuid.uuid4().hex)
    assert run([source], snapshot_root=root).returncode != 0
    assert list(directory.iterdir()) == []
    existing = directory / ('.langbot-export-' + uuid.uuid4().hex)
    existing.mkdir()
    (existing / 'keep').write_bytes(b'keep')
    assert run([source], snapshot_root=existing).returncode != 0
    assert (existing / 'keep').read_bytes() == b'keep'


@pytest.mark.parametrize('termination', ['terminate', 'kill'])
def test_interrupted_snapshot_is_recoverable_from_early_journal(tmp_path, termination):
    import time

    first, second = tmp_path / 'first', tmp_path / 'second'
    first.write_bytes(b'first original')
    second.write_bytes(b'second original')
    root = tmp_path / ('.langbot-export-' + uuid.uuid4().hex)
    waiting = tmp_path / 'waiting'
    pause_before_second_read = f"""
import os, time
_original_open = os.open
def blocking_open(path, *args, **kwargs):
    if path == 'second':
        with open({str(waiting)!r}, 'w') as marker:
            marker.write('waiting')
        time.sleep(60)
    return _original_open(path, *args, **kwargs)
os.open = blocking_open
"""
    script = selected_files_script(
        [str(first), str(second)],
        max_file_bytes=100,
        max_total_bytes=200,
        snapshot_root=str(root),
    )
    process = subprocess.Popen(
        [sys.executable, '-c', pause_before_second_read + script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5
        while not waiting.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert waiting.exists(), process.communicate(timeout=1)
        assert len(list(root.glob('*.bin'))) == 1
        getattr(process, termination)()
        process.communicate(timeout=5)
        with (root / '.manifest.jsonl').open('ab') as journal:
            journal.write(b'{"temporary":')
        cleaned = cleanup_snapshot(root)
        assert cleaned.returncode == 0, cleaned.stderr
        assert not root.exists()
        assert first.read_bytes() == b'first original'
        assert second.read_bytes() == b'second original'
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_snapshot_cleanup_rejects_wrong_root_identity(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'original')
    root = tmp_path / ('.langbot-export-' + uuid.uuid4().hex)
    result = run([source], snapshot_root=root)
    assert result.returncode == 0, result.stderr
    journal = root / '.manifest.jsonl'
    lines = journal.read_bytes().splitlines(keepends=True)
    header = json.loads(lines[0])
    header['root'] = [0, 0]
    journal.write_bytes((json.dumps(header) + '\n').encode() + b''.join(lines[1:]))
    assert cleanup_snapshot(root).returncode != 0
    assert len(list(root.glob('*.bin'))) == 1
    assert source.read_bytes() == b'original'


@pytest.mark.parametrize('interruption', ['payload', 'directory'])
def test_snapshot_cleanup_can_resume_after_interruption(tmp_path, interruption):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.write_bytes(b'first original')
    second.write_bytes(b'second original')
    root = tmp_path / ('.langbot-export-' + uuid.uuid4().hex)
    assert run([first, second], snapshot_root=root).returncode == 0
    prefix = """
import os
original_unlink = os.unlink
def interrupted_unlink(name, *args, **kwargs):
    original_unlink(name, *args, **kwargs)
    if name.endswith('.bin'):
        os._exit(91)
def interrupted_rmdir(*args, **kwargs):
    os._exit(91)
"""
    prefix += 'os.unlink = interrupted_unlink\n' if interruption == 'payload' else 'os.rmdir = interrupted_rmdir\n'
    result = subprocess.run(
        [sys.executable, '-c', prefix + selected_files_cleanup_script(str(root))],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 91
    if interruption == 'payload':
        assert (root / '.manifest.jsonl').exists()
        assert len(list(root.glob('*.bin'))) == 1
    else:
        assert list(root.iterdir()) == []
    cleaned = cleanup_snapshot(root)
    assert cleaned.returncode == 0, cleaned.stderr
    assert not root.exists()
    assert first.read_bytes() == b'first original'
    assert second.read_bytes() == b'second original'
