from __future__ import annotations

import pytest

from langbot.pkg.platform.sources import matrix


def test_matrix_base64_decode_is_bounded(monkeypatch):
    monkeypatch.setattr(matrix, '_MAX_MATRIX_MEDIA_BYTES', 4)

    with pytest.raises(ValueError, match='exceeds'):
        matrix._decode_matrix_base64_limited('A' * 12)


def test_matrix_local_file_read_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix, '_MAX_MATRIX_MEDIA_BYTES', 4)
    path = tmp_path / 'large.bin'
    path.write_bytes(b'12345')

    with pytest.raises(ValueError, match='exceeds'):
        matrix._read_matrix_file_limited(str(path))
