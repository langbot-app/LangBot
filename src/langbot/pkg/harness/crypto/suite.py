"""HTS1 key derivation and authenticated encryption primitives."""

import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from nacl import bindings

SUITE = 'HTS1-X25519-Ed25519-HKDF-SHA256-XChaCha20Poly1305'
INFO = b'langbot-harness-hts1'
WINDOW = 1024
TS_SKEW = 120
KEY_LENGTH = 32
NONCE_LENGTH = bindings.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES


def derive(ikm: bytes, kid: str, transcript: bytes) -> tuple[bytes, bytes, bytes]:
    """Derive client-to-host, host-to-client, and confirmation keys."""
    salt = hashlib.sha256(INFO + kid.encode('utf-8') + transcript).digest()
    output = HKDF(algorithm=hashes.SHA256(), length=KEY_LENGTH * 3, salt=salt, info=INFO).derive(ikm)
    return output[:KEY_LENGTH], output[KEY_LENGTH : KEY_LENGTH * 2], output[KEY_LENGTH * 2 :]


def _nonce(seq: int) -> bytes:
    if isinstance(seq, bool) or not isinstance(seq, int) or not 0 <= seq < 2**64:
        raise ValueError('seq must be an unsigned 64-bit integer')
    return seq.to_bytes(NONCE_LENGTH, 'big')


def seal(key: bytes, seq: int, plaintext: bytes) -> bytes:
    """Encrypt a payload using the protocol's sequence-derived nonce."""
    if len(key) != KEY_LENGTH:
        raise ValueError('key must be 32 bytes')
    return bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(plaintext, None, _nonce(seq), key)


def open_(key: bytes, seq: int, ciphertext: bytes) -> bytes:
    """Authenticate and decrypt a payload using the protocol's sequence nonce."""
    if len(key) != KEY_LENGTH:
        raise ValueError('key must be 32 bytes')
    return bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(ciphertext, None, _nonce(seq), key)
