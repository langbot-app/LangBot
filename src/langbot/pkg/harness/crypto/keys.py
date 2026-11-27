"""Generation and encrypted-at-rest handling for Harness instance keys."""

import base64
import json
import secrets

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode('ascii')


def generate_key_material(wrapping_key: bytes, *, kid: str | None = None) -> dict[str, str]:
    """Create one protocol key pair and encrypt private material with Fernet."""
    agreement = x25519.X25519PrivateKey.generate()
    signing = ed25519.Ed25519PrivateKey.generate()
    key_id = kid or f'harness-{secrets.token_urlsafe(12)}'
    private = json.dumps(
        {'x25519': _b64(agreement.private_bytes_raw()), 'ed25519': _b64(signing.private_bytes_raw())},
        separators=(',', ':'),
    ).encode()
    return {
        'kid': key_id,
        'x25519_pub': _b64(agreement.public_key().public_bytes_raw()),
        'ed25519_pub': _b64(signing.public_key().public_bytes_raw()),
        'priv_ciphertext': Fernet(wrapping_key).encrypt(private).decode('ascii'),
    }
