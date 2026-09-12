"""Second-factor TOTP (RFC 6238) enrolment, verification and recovery.

This service backs the optional TOTP second factor for LangBot Accounts:

* the shared secret is encrypted at rest with a Fernet key derived from the
  instance JWT secret via HKDF, and is never persisted in plaintext;
* recovery codes are stored only as salted PBKDF2-HMAC-SHA256 digests;
* the plaintext secret and recovery codes leave the server exactly once, in the
  enrolment response.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import datetime
import hashlib
import hmac
import json
import logging
import secrets
import struct
import time
import typing
import uuid

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....entity.persistence import totp
from ....entity.persistence import user

if typing.TYPE_CHECKING:
    from ....core.app import Application

_logger = logging.getLogger(__name__)

# RFC 6238 parameters. Six digits and a 30 second step are what every common
# authenticator app (Google Authenticator, Authy, 1Password, ...) defaults to.
_TOTP_DIGITS = 6
_TOTP_STEP_SECONDS = 30
# Accept one step of clock skew in either direction, which tolerates small
# device clock drift without materially widening the brute-force window.
_TOTP_WINDOW_STEPS = 1
_RECOVERY_CODE_COUNT = 10
# 10 groups drawn from 32 symbols provide 50 bits of entropy per recovery code.
_RECOVERY_CODE_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
_RECOVERY_CODE_LENGTH = 10
# Recovery codes are stored only as salted PBKDF2-HMAC-SHA256 digests. The work
# factor is intentionally high: guessing is already infeasible against 50 bits of
# entropy, and the slow KDF keeps a dumped database from being attacked cheaply.
# Hashing runs off the event loop, so this is a latency cost paid only at
# enrolment / regeneration / redemption.
_RECOVERY_CODE_KDF_ITERATIONS = 300_000


class TotpAlreadyEnabledError(ValueError):
    """Raised when enrolling an Account that already has TOTP enabled."""

    code = 'totp_already_enabled'


class TotpNotEnabledError(ValueError):
    """Raised when an operation requires an enabled TOTP credential."""

    code = 'totp_not_enabled'


class TotpInvalidCodeError(ValueError):
    """Raised when a supplied TOTP or recovery code fails verification."""

    code = 'totp_invalid_code'


@dataclasses.dataclass(frozen=True, slots=True)
class TotpEnrollment:
    """Result of starting (or restarting) TOTP enrolment for an Account."""

    secret: str
    otpauth_uri: str


class TotpService:
    """Second-factor TOTP enrolment, verification and recovery for Accounts.

    Nothing usable is persisted in plaintext:

    * The shared TOTP secret is encrypted at rest with a Fernet key derived from
      the instance JWT secret via HKDF, so a leaked database file alone does not
      expose live secrets (the attacker additionally needs ``config.yaml``).
    * Recovery codes are stored only as salted PBKDF2-HMAC-SHA256 digests and are
      consumed one at a time.
    * The plaintext secret / recovery codes leave the server exactly once, in the
      enrolment response, and are never stored or logged server-side.
    """

    ap: Application

    def __init__(self, ap: Application) -> None:
        self.ap = ap

    # -- storage helpers -------------------------------------------------

    def _session_factory(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(self.ap.persistence_mgr.get_db_engine(), expire_on_commit=False)

    def _encryption_key(self) -> bytes:
        """Derive a stable 32-byte Fernet key from the instance JWT secret.

        HKDF-SHA256 with a fixed domain-separation salt keeps the key stable
        across restarts and distinct from the JWT signing secret. The key
        material is NOT stored in the database, so a leaked ``langbot.db`` alone
        cannot decrypt the TOTP secrets.
        """
        secret = ''
        try:
            secret = self.ap.instance_config.data['system']['jwt']['secret'] or ''
        except (KeyError, TypeError):
            secret = ''
        if not secret:
            # Defence in depth: a missing JWT secret must not silently produce a
            # well-known encryption key. This should never happen because
            # GenKeysStage seeds it, but failing closed is safer than encrypting
            # with a predictable key. The caller maps this to an invalid-code
            # failure, so no plaintext is ever persisted.
            raise TotpInvalidCodeError('Instance JWT secret unavailable')

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        # HKDF enforces the label internally, so include it as `info`.
        derived = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'langbot-totp-v1',
            info=b'langbot-totp-secret-encryption',
        ).derive(secret.encode('utf-8'))
        return base64.urlsafe_b64encode(derived)

    def _encrypt_secret(self, secret: str) -> str:
        from cryptography.fernet import Fernet

        return Fernet(self._encryption_key()).encrypt(secret.encode('utf-8')).decode('ascii')

    def _decrypt_secret(self, token: str) -> str:
        from cryptography.fernet import Fernet, InvalidToken

        try:
            return Fernet(self._encryption_key()).decrypt(token.encode('ascii')).decode('utf-8')
        except (InvalidToken, ValueError) as exc:
            raise TotpInvalidCodeError('Stored TOTP secret cannot be decrypted') from exc

    # -- RFC 6238 primitives ---------------------------------------------

    @staticmethod
    def generate_secret() -> str:
        """Return a fresh base32 secret (160 bits, the RFC 4226 recommendation)."""
        return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')

    @staticmethod
    def _hotp(secret: str, counter: int) -> str:
        padding = '=' * (-len(secret) % 8)
        key = base64.b32decode(secret.upper() + padding)
        msg = struct.pack('>Q', counter)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        binary = struct.unpack('>I', digest[offset : offset + 4])[0] & 0x7FFFFFFF
        return str(binary % (10**_TOTP_DIGITS)).zfill(_TOTP_DIGITS)

    @classmethod
    def generate_code(cls, secret: str, at: float | None = None) -> str:
        """Return the TOTP code for ``secret`` at the given (or current) time."""
        counter = int((at if at is not None else time.time()) // _TOTP_STEP_SECONDS)
        return cls._hotp(secret, counter)

    @classmethod
    def verify_code(cls, secret: str, code: str, at: float | None = None) -> bool:
        """Constant-time check of a user-supplied code within the skew window."""
        candidate = (code or '').strip().replace(' ', '')
        if not candidate.isdigit() or len(candidate) != _TOTP_DIGITS:
            return False
        now = at if at is not None else time.time()
        counter = int(now // _TOTP_STEP_SECONDS)
        for offset in range(-_TOTP_WINDOW_STEPS, _TOTP_WINDOW_STEPS + 1):
            expected = cls._hotp(secret, counter + offset)
            if hmac.compare_digest(expected, candidate):
                return True
        return False

    @staticmethod
    def build_otpauth_uri(secret: str, account_name: str, issuer: str = 'LangBot') -> str:
        """Build the otpauth:// URI an authenticator app scans from the QR code."""
        from urllib.parse import quote, urlencode

        label = quote(f'{issuer}:{account_name}')
        params = urlencode(
            {
                'secret': secret,
                'issuer': issuer,
                'algorithm': 'SHA1',
                'digits': _TOTP_DIGITS,
                'period': _TOTP_STEP_SECONDS,
            }
        )
        return f'otpauth://totp/{label}?{params}'

    @staticmethod
    def build_qr_svg(otpauth_uri: str) -> str:
        """Render the otpauth URI to an inline SVG QR code.

        SVG keeps the response text-only so the frontend can drop it straight
        into a dialog without byte-encoding a PNG data URL.
        """
        import qrcode
        import qrcode.image.svg

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
            image_factory=qrcode.image.svg.SvgPathImage,
        )
        qr.add_data(otpauth_uri)
        qr.make(fit=True)
        image = qr.make_image()
        import io

        buffer = io.BytesIO()
        image.save(buffer)
        return buffer.getvalue().decode('utf-8')

    # -- recovery codes ---------------------------------------------------

    @staticmethod
    def _normalise_recovery_code(code: str) -> str:
        return (code or '').strip().upper().replace('-', '').replace(' ', '')

    @classmethod
    def _hash_recovery_code(cls, code: str, *, salt: bytes | None = None) -> str:
        """Return a self-describing PBKDF2-HMAC-SHA256 digest of a recovery code.

        The format is ``pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>`` so the
        work factor is stored alongside the digest and can be raised later
        without invalidating existing codes. Salted and slow, so a database dump
        does not allow offline brute-forcing of recovery codes.
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            'sha256',
            cls._normalise_recovery_code(code).encode('utf-8'),
            salt,
            _RECOVERY_CODE_KDF_ITERATIONS,
        )
        return f'pbkdf2_sha256${_RECOVERY_CODE_KDF_ITERATIONS}${salt.hex()}${digest.hex()}'

    @staticmethod
    def _split_recovery_digest(stored: str) -> tuple[int, bytes, bytes] | None:
        parts = (stored or '').split('$')
        if len(parts) != 4 or parts[0] != 'pbkdf2_sha256':
            return None
        try:
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            digest = bytes.fromhex(parts[3])
        except ValueError:
            return None
        return iterations, salt, digest

    @staticmethod
    def _random_recovery_code() -> str:
        """Return one random recovery code from the unambiguous alphabet."""
        alphabet = _RECOVERY_CODE_ALPHABET
        return ''.join(secrets.choice(alphabet) for _ in range(_RECOVERY_CODE_LENGTH))

    @classmethod
    async def generate_recovery_codes(cls) -> tuple[list[str], list[str]]:
        """Return ``(plaintext_codes, hashed_codes)`` for one enrolment."""
        plaintext: list[str] = []
        hashed: list[str] = []
        for _ in range(_RECOVERY_CODE_COUNT):
            code = cls._random_recovery_code()
            plaintext.append(code)
            # Offload the expensive KDF so 10 codes do not stall the event loop.
            hashed.append(await asyncio.to_thread(cls._hash_recovery_code, code))
        return plaintext, hashed

    # -- persistence ------------------------------------------------------

    @staticmethod
    def _credential_statement(account_uuid: str) -> typing.Any:
        """Build the SELECT that loads an Account's TOTP credential row."""
        entity = totp.TotpCredential
        return sqlalchemy.select(entity).where(entity.account_uuid == account_uuid)

    async def get_credential(self, account_uuid: str) -> totp.TotpCredential | None:
        """Load the (single) TOTP credential row for an Account, if any."""
        statement = self._credential_statement(account_uuid)
        async with self._session_factory()() as session:
            return await session.scalar(statement)

    async def is_enabled(self, account_uuid: str) -> bool:
        """Return whether the Account has a confirmed, enabled TOTP credential."""
        credential = await self.get_credential(account_uuid)
        return bool(credential and credential.enabled)

    async def begin_enrollment(self, account: user.User) -> tuple[TotpEnrollment, list[str]]:
        """Create or replace a pending TOTP secret and return recovery codes.

        A previous *enabled* credential is left untouched until the new secret
        is confirmed, so a failed re-enrolment cannot lock the account out.
        """
        secret = self.generate_secret()
        uri = self.build_otpauth_uri(secret, account_name=account.user)
        plaintext_codes, hashed_codes = await self.generate_recovery_codes()

        async with self._session_factory()() as session:
            async with session.begin():
                credential = await session.scalar(self._credential_statement(account.uuid))
                if credential is None:
                    credential = totp.TotpCredential(
                        uuid=str(uuid.uuid4()),
                        account_uuid=account.uuid,
                        secret_encrypted=self._encrypt_secret(secret),
                        account_name=account.user,
                        enabled=False,
                        recovery_codes=json.dumps(hashed_codes),
                    )
                    session.add(credential)
                elif not credential.enabled:
                    credential.secret_encrypted = self._encrypt_secret(secret)
                    credential.account_name = account.user
                    credential.recovery_codes = json.dumps(hashed_codes)
                else:
                    raise TotpAlreadyEnabledError('TOTP is already enabled for this account')
                await session.flush()

        return TotpEnrollment(secret=secret, otpauth_uri=uri), plaintext_codes

    async def confirm_enrollment(self, account_uuid: str, code: str) -> None:
        """Verify the first code and flip the credential to enabled."""
        credential = await self.get_credential(account_uuid)
        if credential is None:
            raise TotpNotEnabledError('No pending TOTP enrolment found')
        if credential.enabled:
            raise TotpAlreadyEnabledError('TOTP is already enabled for this account')

        try:
            code_matches = self.verify_code(self._decrypt_secret(credential.secret_encrypted), code)
        except TotpInvalidCodeError:
            code_matches = False
        if not code_matches:
            raise TotpInvalidCodeError('Invalid verification code')

        async with self._session_factory()() as session:
            async with session.begin():
                record = await session.scalar(self._credential_statement(account_uuid))
                if record is None:
                    raise TotpNotEnabledError('No pending TOTP enrolment found')
                record.enabled = True
                record.last_used_at = datetime.datetime.now()

    async def verify_for_account(self, account_uuid: str, code: str) -> bool:
        """Validate a live TOTP code for an enabled credential."""
        credential = await self.get_credential(account_uuid)
        if credential is None or not credential.enabled:
            return False
        try:
            secret = self._decrypt_secret(credential.secret_encrypted)
        except TotpInvalidCodeError:
            return False
        if not self.verify_code(secret, code):
            return False
        async with self._session_factory()() as session:
            async with session.begin():
                record = await session.scalar(self._credential_statement(account_uuid))
                if record is not None:
                    record.last_used_at = datetime.datetime.now()
        return True

    @classmethod
    def _match_recovery_code(cls, code: str, hashed_codes: list[str]) -> int:
        """Return the index of the matching digest, or -1. Constant-time per entry."""
        candidate = cls._normalise_recovery_code(code)
        for index, stored in enumerate(hashed_codes):
            parsed = cls._split_recovery_digest(stored)
            if parsed is None:
                continue
            iterations, salt, expected = parsed
            digest = hashlib.pbkdf2_hmac('sha256', candidate.encode('utf-8'), salt, iterations)
            if hmac.compare_digest(digest, expected):
                return index
        return -1

    async def redeem_recovery_code(self, account_uuid: str, code: str) -> bool:
        """Consume a one-time recovery code for password reset fallback."""
        credential = await self.get_credential(account_uuid)
        if credential is None:
            return False

        hashed_codes: list[str] = []
        if credential.recovery_codes:
            try:
                parsed = json.loads(credential.recovery_codes)
                if isinstance(parsed, list):
                    hashed_codes = [str(item) for item in parsed]
            except (ValueError, TypeError):
                hashed_codes = []

        # Recomputing PBKDF2 for up to 10 salted digests is CPU-bound; keep it
        # off the event loop so a recovery attempt cannot stall other requests.
        matched_index = await asyncio.to_thread(self._match_recovery_code, code or '', hashed_codes)
        if matched_index < 0:
            return False

        remaining = hashed_codes[:matched_index] + hashed_codes[matched_index + 1 :]
        async with self._session_factory()() as session:
            async with session.begin():
                record = await session.scalar(self._credential_statement(account_uuid))
                if record is not None:
                    record.recovery_codes = json.dumps(remaining)
                    record.last_used_at = datetime.datetime.now()
        return True

    async def regenerate_recovery_codes(self, account_uuid: str) -> tuple[None, list[str]]:
        """Replace the recovery codes for an enabled credential.

        The caller is responsible for proving possession of a valid TOTP code
        first; this method only swaps the stored digests for a fresh set and
        returns the plaintext codes for one-time display.
        """
        credential = await self.get_credential(account_uuid)
        if credential is None or not credential.enabled:
            raise TotpNotEnabledError('TOTP is not enabled for this account')

        plaintext_codes, hashed_codes = await self.generate_recovery_codes()
        async with self._session_factory()() as session:
            async with session.begin():
                record = await session.scalar(self._credential_statement(account_uuid))
                if record is None:
                    raise TotpNotEnabledError('TOTP is not enabled for this account')
                record.recovery_codes = json.dumps(hashed_codes)
                record.updated_at = datetime.datetime.now()
        return None, plaintext_codes

    async def disable(self, account_uuid: str, code: str) -> bool:
        """Remove TOTP after the caller proves possession of a valid factor."""
        credential = await self.get_credential(account_uuid)
        if credential is None or not credential.enabled:
            raise TotpNotEnabledError('TOTP is not enabled for this account')

        try:
            secret = self._decrypt_secret(credential.secret_encrypted)
            code_matches = self.verify_code(secret, code)
        except TotpInvalidCodeError:
            code_matches = False
        if not code_matches:
            raise TotpInvalidCodeError('Invalid verification code')

        async with self._session_factory()() as session:
            async with session.begin():
                record = await session.scalar(self._credential_statement(account_uuid))
                if record is not None:
                    await session.delete(record)
        return True

    async def remaining_recovery_codes(self, account_uuid: str) -> int:
        """Return how many unused recovery codes remain for the Account."""
        credential = await self.get_credential(account_uuid)
        if credential is None or not credential.recovery_codes:
            return 0
        try:
            parsed = json.loads(credential.recovery_codes)
        except (ValueError, TypeError):
            return 0
        return len(parsed) if isinstance(parsed, list) else 0
