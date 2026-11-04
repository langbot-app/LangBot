"""Exercise the exact scripts sent to Docker/E2B, without a host mirror."""

import base64
import hashlib
import json
import subprocess
import sys

import pytest

from langbot.pkg.box.file_transfer import CHUNK_BYTES, directory_snapshot_script, import_chunk_script


def run_script(script):
    return subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)


def test_chunked_import_is_complete_and_never_overwrites_other_content(tmp_path):
    data = bytes(range(256)) * 1400
    digest = hashlib.sha256(data).hexdigest()
    target = tmp_path / 'inbox' / 'run'
    for offset in range(0, len(data), CHUNK_BYTES):
        chunk = data[offset : offset + CHUNK_BYTES]
        result = run_script(
            import_chunk_script(
                str(target), '.import-test', 'input.bin', base64.b64encode(chunk).decode(), offset, len(data), digest
            )
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['complete'] == (offset + len(chunk) == len(data))
        if offset + len(chunk) != len(data):
            assert not (target / 'input.bin').exists()
    assert (target / 'input.bin').read_bytes() == data
    other = b'changed'
    result = run_script(
        import_chunk_script(
            str(target),
            '.other',
            'input.bin',
            base64.b64encode(other).decode(),
            0,
            len(other),
            hashlib.sha256(other).hexdigest(),
        )
    )
    assert result.returncode != 0
    assert (target / 'input.bin').read_bytes() == data


def test_snapshot_reads_only_selected_draft_and_rejects_links(tmp_path):
    draft = tmp_path / 'draft'
    draft.mkdir()
    (draft / 'SKILL.md').write_text('draft')
    (tmp_path / 'other-agent.txt').write_text('private')
    result = run_script(directory_snapshot_script(str(draft)))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [{'name': 'SKILL.md', 'b64': base64.b64encode(b'draft').decode()}]
    (draft / 'leak').symlink_to(tmp_path / 'other-agent.txt')
    assert run_script(directory_snapshot_script(str(draft))).returncode != 0
    (tmp_path / 'linked-draft').symlink_to(draft)
    assert run_script(directory_snapshot_script(str(tmp_path / 'linked-draft'))).returncode != 0


@pytest.mark.parametrize('limit', [{'max_files': 0}, {'max_bytes': 1}])
def test_snapshot_enforces_transfer_limits(tmp_path, limit):
    (tmp_path / 'file').write_bytes(b'content')
    assert run_script(directory_snapshot_script(str(tmp_path), **limit)).returncode != 0
