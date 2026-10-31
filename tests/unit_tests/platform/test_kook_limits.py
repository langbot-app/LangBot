from __future__ import annotations

import json
import zlib

import pytest

from langbot.pkg.platform.sources import kook


def test_kook_gateway_decoder_accepts_raw_and_compressed_json():
    payload = {'s': 1, 'd': {'session_id': 'session-a'}}
    encoded = json.dumps(payload).encode()

    assert kook._decode_gateway_message(encoded) == payload
    assert kook._decode_gateway_message(zlib.compress(encoded)) == payload


def test_kook_gateway_decoder_rejects_decompression_bomb(monkeypatch):
    monkeypatch.setattr(kook, '_KOOK_MAX_GATEWAY_MESSAGE_BYTES', 1024)
    compressed = zlib.compress(b'x' * 1025)

    with pytest.raises(ValueError, match='decompressed size limit'):
        kook._decode_gateway_message(compressed)
