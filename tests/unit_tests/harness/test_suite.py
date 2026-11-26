import pytest
from nacl.exceptions import CryptoError

from langbot.pkg.harness.crypto.suite import derive, open_, seal


def test_derive_is_deterministic_and_separates_directions():
    keys = derive(b'input key material', 'key-1', b'transcript')
    assert keys == derive(b'input key material', 'key-1', b'transcript')
    assert len(set(keys)) == 3
    assert keys != derive(b'input key material', 'key-2', b'transcript')


def test_seal_open_round_trip_and_authentication():
    key = derive(b'input key material', 'key-1', b'transcript')[0]
    ciphertext = seal(key, 7, b'private payload')
    assert open_(key, 7, ciphertext) == b'private payload'
    with pytest.raises(CryptoError):
        open_(key, 8, ciphertext)


@pytest.mark.parametrize('seq', [-1, 2**64, True, '1'])
def test_sequence_must_be_unsigned_integer(seq):
    key = b'k' * 32
    with pytest.raises(ValueError, match='unsigned 64-bit'):
        seal(key, seq, b'x')


def test_key_must_be_32_bytes():
    with pytest.raises(ValueError, match='32 bytes'):
        seal(b'short', 0, b'x')
