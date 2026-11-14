import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid
import zipfile

import pytest

from langbot.pkg.box.draft_files import skill_draft_script
from langbot.pkg.box.selected_files import selected_files_cleanup_script


def export_draft(source, root, prefix=''):
    return subprocess.run(
        [sys.executable, '-c', prefix + skill_draft_script(str(source), str(root))],
        capture_output=True,
        text=True,
        timeout=10,
    )


def cleanup(root):
    return subprocess.run(
        [sys.executable, '-c', selected_files_cleanup_script(str(root))],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_draft_archive_preserves_resources_modes_and_original(tmp_path):
    source = tmp_path / 'draft'
    source.mkdir()
    (source / 'SKILL.md').write_text('---\nname: demo\ndescription: Demo\n---\nUse resources\n')
    (source / 'scripts').mkdir()
    script = source / 'scripts' / 'run.sh'
    script.write_bytes(b'#!/bin/sh\nprintf ready\n')
    script.chmod(0o755)
    (source / 'resource.bin').write_bytes(bytes(range(256)))
    root = tmp_path / ('.langbot-export-' + uuid.uuid4().hex)
    result = export_draft(source, root)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    archive_path = Path(receipt['snapshot_path'])
    content = archive_path.read_bytes()
    assert archive_path.parent == root
    assert receipt['size'] == len(content)
    assert receipt['sha256'] == hashlib.sha256(content).hexdigest()
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.read('resource.bin') == bytes(range(256))
        assert archive.read('scripts/run.sh') == b'#!/bin/sh\nprintf ready\n'
        assert stat.S_IMODE(archive.getinfo('scripts/run.sh').external_attr >> 16) == 0o755
        assert set(archive.namelist()) == {'SKILL.md', 'resource.bin', 'scripts/', 'scripts/run.sh'}
    assert cleanup(root).returncode == 0
    assert not root.exists()
    assert script.read_bytes() == b'#!/bin/sh\nprintf ready\n'


@pytest.mark.parametrize('unsafe', ['symlink', 'hardlink', 'fifo', 'file_size', 'entries', 'archive_size'])
def test_draft_rejection_retains_original_and_removes_snapshot(tmp_path, unsafe):
    source = tmp_path / 'draft'
    source.mkdir()
    original = source / 'original'
    original.write_bytes(b'original')
    target = source / 'unsafe'
    if unsafe == 'symlink':
        target.symlink_to(original)
    elif unsafe == 'hardlink':
        os.link(original, target)
    elif unsafe == 'fifo':
        os.mkfifo(target)
    elif unsafe == 'file_size':
        with target.open('wb') as output:
            output.truncate(16 * 1024 * 1024 + 1)
    elif unsafe == 'archive_size':
        for index in range(2):
            with (source / str(index)).open('wb') as output:
                output.truncate(11 * 1024 * 1024)
    else:
        for index in range(512):
            (source / str(index)).touch()
    root = tmp_path / ('.langbot-export-' + uuid.uuid4().hex)
    result = export_draft(source, root)
    assert result.returncode != 0
    assert original.read_bytes() == b'original'
    assert not root.exists()


def test_interrupted_draft_snapshot_has_recoverable_journal(tmp_path):
    source = tmp_path / 'draft'
    source.mkdir()
    (source / 'payload').write_bytes(b'keep')
    root = tmp_path / ('.langbot-export-' + uuid.uuid4().hex)
    interrupt = """
import os
original_open = os.open
def interrupt_read(path, *args, **kwargs):
    if path == 'payload':
        os._exit(91)
    return original_open(path, *args, **kwargs)
os.open = interrupt_read
"""
    result = export_draft(source, root, interrupt)
    assert result.returncode == 91
    assert root.exists()
    result = cleanup(root)
    assert result.returncode == 0, result.stderr
    assert not root.exists()
    assert (source / 'payload').read_bytes() == b'keep'
