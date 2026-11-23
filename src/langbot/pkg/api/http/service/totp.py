from __future__ import annotations

import base64
import dataclasses
import datetime
import hashlib
import hmac
import io
import secrets
import time
import typing
import uuid as uuid_lib
from urllib.parse import quote as url_quote

import qrcode
import sqlalchemy
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....entity.persistence import totp as totp_entity
from ....entity.persistence import user

if typing.TYPE_CHECKING:
    from ....core.app import Application


# HKDF context: rotating the wrapping key means bumping the key version, never
# re-using an existing derivation context.
_HKDF_SALT = b'langbot.totp.secret.v1'
_HKDF_INFO = b'langbot-totp-secret-encryption'
_HKDF_LENGTH = 32

# Recovery codes: PBKDF2-HMAC-SHA256. Only the digest is ever persisted.
_RECOVERY_CODE_ALGORITHM = 'pbkdf2_hmac_sha256'
_PBKDF2_ITERATIONS = 600_000
_PBKDF2_SALT_BYTES = 16
_RECOVERY_CODE_COUNT = 4
_RECOVERY_CODE_GROUPS = 4
_RECOVERY_CODE_GROUP_LENGTH = 5

# Login second-factor challenge lifetime and admission bounds.
_TOTP_CHALLENGE_TTL_SECONDS = 5 * 60
_TOTP_CHALLENGE_MAX_ENTRIES = 4096
_TOTP_MAX_ATTEMPTS = 5

# Unambiguous base32 alphabet used for recovery codes (no 0/O/1/I confusion).
_RECOVERY_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def _utc_now_naive() -> datetime.datetime:
    """UTC now without tzinfo, matching the credential ``timestamp`` columns.

    The TOTP tables store ``timestamp without time zone``. asyncpg rejects an
    offset-aware value for such a column (SQLite accepts it, which is why this
    only surfaced on PostgreSQL), so every write converts at the boundary.
    """

    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class TotpError(ValueError):
    """Base class for TOTP second-factor failures."""

    code = 'totp_error'


class TotpNotEnrolledError(TotpError):
    code = 'totp_not_enrolled'


class TotpAlreadyEnrolledError(TotpError):
    code = 'totp_already_enrolled'


class TotpInvalidCodeError(TotpError):
    code = 'totp_invalid_code'


class TotpRequiredError(TotpError):
    """Raised when the password flow still requires a second factor."""

    code = 'totp_required'


class TotpChallengeError(TotpError):
    code = 'totp_challenge_invalid'


@dataclasses.dataclass(frozen=True, slots=True)
class TotpChallengeData:
    account_uuid: str
    user_email: str
    expires_at: float
    attempts: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class TotpEnrollment:
    """Result of starting an enrolment.

    The shared secret never leaves the backend: only a server-rendered QR code
    (as a ``data:`` URL) is handed to the client so the operator can scan it into
    an authenticator. The secret itself is persisted solely as a ciphertext token
    and is never returned in plaintext.
    """

    uuid: str
    qr_code_data_url: str
    algorithm: str
    digits: int
    period: int


@dataclasses.dataclass(frozen=True, slots=True)
class TotpRecoveryCodes:
    """Recovery codes returned exactly once, at confirmation or regeneration."""

    codes: list[str]


def _derive_wrapping_key(jwt_secret: str, key_version: int) -> bytes:
    """HKDF-SHA256 derivation of the Fernet key from the instance JWT secret."""

    if not jwt_secret:
        raise TotpError('Instance JWT secret is not configured')
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_HKDF_LENGTH,
        salt=_HKDF_SALT,
        info=_HKDF_INFO + b'.v' + str(int(key_version)).encode('ascii'),
    )
    # Fernet requires a url-safe base64 encoded 32-byte key.
    return base64.urlsafe_b64encode(hkdf.derive(jwt_secret.encode('utf-8')))


def _generate_totp_secret(length: int = 32) -> str:
    """Generate a base32 TOTP shared secret from a CSPRNG."""

    return base64.b32encode(secrets.token_bytes(length)).decode('ascii').rstrip('=')


def _normalize_code(value: typing.Any) -> str:
    return ''.join(ch for ch in str(value or '').upper() if ch.isalnum())


def _hotp(secret: bytes, counter: int, digits: int) -> str:
    """RFC 4226 HMAC-SHA1 dynamic truncation."""

    digest = hmac.new(secret, counter.to_bytes(8, byteorder='big'), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = (
        (digest[offset] & 0x7F) << 24
        | (digest[offset + 1] & 0xFF) << 16
        | (digest[offset + 2] & 0xFF) << 8
        | (digest[offset + 3] & 0xFF)
    )
    return str(truncated % (10**digits)).zfill(digits)


def _decode_secret(secret: str) -> bytes:
    padding = '=' * ((8 - len(secret) % 8) % 8)
    try:
        return base64.b32decode(secret.upper() + padding)
    except Exception as exc:  # noqa: BLE001 - surface as a domain error
        raise TotpError('TOTP secret is not valid base32') from exc


def _totp_counter(period: int, *, at: float | None = None) -> int:
    """RFC 6238 time step counter."""

    moment = time.time() if at is None else at
    return int(moment // max(1, period))


def _pbkdf2_digest(code: str, salt: str, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """PBKDF2-HMAC-SHA256 digest of a recovery code, hex encoded."""

    return hashlib.pbkdf2_hmac(
        'sha256',
        _normalize_code(code).encode('utf-8'),
        salt.encode('utf-8'),
        iterations,
    ).hex()


def _generate_recovery_codes() -> list[str]:
    """Human-transcribable single-use recovery codes."""

    length = _RECOVERY_CODE_GROUPS * _RECOVERY_CODE_GROUP_LENGTH
    codes: list[str] = []
    for _ in range(_RECOVERY_CODE_COUNT):
        raw = ''.join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(length))
        codes.append(
            '-'.join(raw[i : i + _RECOVERY_CODE_GROUP_LENGTH] for i in range(0, length, _RECOVERY_CODE_GROUP_LENGTH))
        )
    return codes


def build_totp_uri(secret: str, account: str, issuer: str = 'LangBot') -> str:
    """Build an otpauth:// provisioning URI for an authenticator app."""

    return (
        f'otpauth://totp/{url_quote(account)}?secret={secret}'
        f'&issuer={url_quote(issuer)}&algorithm=SHA1&digits=6&period=30'
    )


def render_totp_qr_data_url(otpauth_uri: str) -> str:
    """Render a provisioning URI as a PNG ``data:`` URL.

    The QR code is produced on the server so the shared secret never has to
    travel to the browser as a plaintext value.
    """

    image = qrcode.QRCode(border=1, box_size=8)
    image.add_data(otpauth_uri)
    image.make(fit=True)
    picture = image.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    picture.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


class TotpService:
    """TOTP enrolment, verification, disablement and recovery-code use.

    Security invariants enforced here:
    * the shared secret is only ever persisted as a Fernet token whose key is
      derived (HKDF-SHA256) from the instance JWT secret;
    * recovery codes are only ever persisted as salted PBKDF2-HMAC-SHA256
      digests and are single-use;
    * the consumed counter advances monotonically so a captured code cannot be
      replayed inside the same time window.
    """

    ap: Application

    def __init__(self, ap: Application) -> None:
        self.ap = ap
        self._challenges: dict[str, TotpChallengeData] = {}

    # ------------------------------------------------------------------
    # configuration / storage helpers
    # ------------------------------------------------------------------
    def _session_factory(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(self.ap.persistence_mgr.get_db_engine(), expire_on_commit=False)

    def _jwt_secret(self) -> str:
        secret = self.ap.instance_config.data['system']['jwt']['secret']
        if not isinstance(secret, str) or not secret:
            raise TotpError('Instance JWT secret is not configured')
        return secret

    def _fernet(self, key_version: int = 1) -> Fernet:
        return Fernet(_derive_wrapping_key(self._jwt_secret(), key_version))

    async def is_enrolled(self, account_uuid: str) -> bool:
        credential = await self.get_credential(account_uuid)
        return credential is not None and credential.confirmed_at is not None

    async def get_credential(self, account_uuid: str) -> totp_entity.TotpCredential | None:
        statement = (
            sqlalchemy.select(totp_entity.TotpCredential)
            .where(
                totp_entity.TotpCredential.account_uuid == account_uuid,
                totp_entity.TotpCredential.disabled_at.is_(None),
            )
            .order_by(totp_entity.TotpCredential.created_at.desc())
            .limit(1)
        )
        async with self._session_factory()() as session:
            return await session.scalar(statement)

    # ------------------------------------------------------------------
    # login second-factor challenge
    # ------------------------------------------------------------------
    async def issue_login_challenge(self, account_uuid: str, user_email: str) -> str:
        """Issue a single-use second-factor challenge for one Account."""

        token = secrets.token_urlsafe(32)
        self._prune_challenges()
        # Bound the challenge table so unauthenticated login attempts cannot
        # grow process memory without limit.
        while len(self._challenges) >= _TOTP_CHALLENGE_MAX_ENTRIES:
            self._challenges.pop(next(iter(self._challenges)), None)
        self._challenges[token] = TotpChallengeData(
            account_uuid=account_uuid,
            user_email=user_email,
            expires_at=time.monotonic() + _TOTP_CHALLENGE_TTL_SECONDS,
        )
        return token

    def consume_login_challenge(self, token: str) -> TotpChallengeData:
        data = self._challenges.get(token)
        if data is None or data.expires_at < time.monotonic():
            self._challenges.pop(token, None)
            raise TotpChallengeError('Invalid or expired second-factor challenge')
        return data

    def complete_login_challenge(self, token: str) -> None:
        self._challenges.pop(token, None)

    def record_failed_attempt(self, token: str) -> None:
        """Count a failed attempt and burn the challenge once the cap is hit."""

        data = self._challenges.get(token)
        if data is None:
            return
        attempts = data.attempts + 1
        if attempts >= _TOTP_MAX_ATTEMPTS:
            self._challenges.pop(token, None)
            return
        self._challenges[token] = dataclasses.replace(data, attempts=attempts)

    def _prune_challenges(self) -> None:
        now = time.monotonic()
        for token in [token for token, data in self._challenges.items() if data.expires_at < now]:
            self._challenges.pop(token, None)

    # ------------------------------------------------------------------
    # enrolment
    # ------------------------------------------------------------------
    async def begin_enrollment(
        self,
        account_uuid: str,
        user_email: str,
        *,
        rotate: bool = False,
        force: bool = False,
    ) -> TotpEnrollment:
        """Create or replace the pending TOTP credential for an Account.

        Any previous unconfirmed attempt is retired and outstanding recovery
        codes are cleared, so a half-finished enrolment can never linger.

        The plaintext secret is discarded after this call: callers only ever
        receive a server-rendered QR code.

        ``force`` is used by Workspace owners/admins to re-bind an Account whose
        authenticator was lost: it retires an already-confirmed credential and
        starts a fresh pending enrolment.
        """

        credential = await self.get_credential(account_uuid)
        if credential is not None and credential.confirmed_at is not None and not force:
            raise TotpAlreadyEnrolledError('TOTP is already enabled for this Account')

        # Reuse an unconfirmed (pending) enrolment instead of minting a new
        # secret. Duplicate requests are normal - React StrictMode invokes
        # effects twice in development and browsers/proxies may retry - and
        # rotating the secret would invalidate the QR code already on screen,
        # making the subsequent confirm_enrollment() call fail with
        # "Invalid TOTP code". Returning the same QR keeps them in sync.
        # An explicit "refresh" passes rotate=True to opt back into rotation.
        if credential is not None and not rotate and not force:
            pending_secret = self._decrypt_secret(credential.secret_ciphertext, credential.key_version)
            return TotpEnrollment(
                uuid=credential.uuid,
                qr_code_data_url=render_totp_qr_data_url(build_totp_uri(pending_secret.decode('ascii'), user_email)),
                algorithm=credential.algorithm,
                digits=credential.digits,
                period=credential.period,
            )

        secret = _generate_totp_secret()
        ciphertext = self._fernet().encrypt(secret.encode('utf-8')).decode('ascii')
        record_uuid = str(uuid_lib.uuid4())

        async with self._session_factory()() as session:
            async with session.begin():
                await session.execute(
                    sqlalchemy.update(totp_entity.TotpCredential)
                    .where(totp_entity.TotpCredential.account_uuid == account_uuid)
                    .values(disabled_at=_utc_now_naive())
                )
                await session.execute(
                    sqlalchemy.delete(totp_entity.TotpRecoveryCode).where(
                        totp_entity.TotpRecoveryCode.account_uuid == account_uuid
                    )
                )
                session.add(
                    totp_entity.TotpCredential(
                        uuid=record_uuid,
                        account_uuid=account_uuid,
                        secret_ciphertext=ciphertext,
                        key_version=1,
                        algorithm='SHA1',
                        digits=6,
                        period=30,
                    )
                )

        # Render the QR code here (and drop the plaintext secret) so the shared
        # secret never crosses the API boundary towards the browser.
        qr_code_data_url = render_totp_qr_data_url(build_totp_uri(secret, user_email))

        return TotpEnrollment(
            uuid=record_uuid,
            qr_code_data_url=qr_code_data_url,
            algorithm='SHA1',
            digits=6,
            period=30,
        )

    async def confirm_enrollment(self, account_uuid: str, code: str) -> TotpRecoveryCodes:
        """Verify the first code, activate the credential and mint recovery codes.

        Recovery codes are returned exactly once; only their salted PBKDF2
        digests are stored.
        """

        credential = await self.get_credential(account_uuid)
        if credential is None:
            raise TotpNotEnrolledError('No pending TOTP enrolment for this Account')
        if credential.confirmed_at is not None:
            raise TotpAlreadyEnrolledError('TOTP is already enabled for this Account')

        counter = self._verify_counter(credential, code)
        codes = _generate_recovery_codes()
        now = _utc_now_naive()

        async with self._session_factory()() as session:
            async with session.begin():
                await session.execute(
                    sqlalchemy.update(totp_entity.TotpCredential)
                    .where(
                        totp_entity.TotpCredential.uuid == credential.uuid,
                        totp_entity.TotpCredential.confirmed_at.is_(None),
                    )
                    .values(confirmed_at=now, last_used_at=now, last_used_counter=counter)
                )
                self._store_recovery_codes(session, account_uuid, credential.uuid, codes)

        return TotpRecoveryCodes(codes=codes)

    async def regenerate_recovery_codes(self, account_uuid: str, code: str) -> TotpRecoveryCodes:
        """Replace all recovery codes, requiring a valid live TOTP code first."""

        credential = await self.get_credential(account_uuid)
        if credential is None or credential.confirmed_at is None:
            raise TotpNotEnrolledError('TOTP is not enabled for this Account')
        if not await self.verify_code(account_uuid, code, allow_recovery=True):
            raise TotpInvalidCodeError('Invalid TOTP code')

        codes = _generate_recovery_codes()
        async with self._session_factory()() as session:
            async with session.begin():
                await session.execute(
                    sqlalchemy.delete(totp_entity.TotpRecoveryCode).where(
                        totp_entity.TotpRecoveryCode.account_uuid == account_uuid
                    )
                )
                self._store_recovery_codes(session, account_uuid, credential.uuid, codes)
        return TotpRecoveryCodes(codes=codes)

    def _store_recovery_codes(
        self,
        session: AsyncSession,
        account_uuid: str,
        credential_uuid: str,
        codes: list[str],
    ) -> None:
        """Persist recovery codes as salted PBKDF2-HMAC-SHA256 digests only."""

        for index, code_value in enumerate(codes):
            salt = secrets.token_hex(_PBKDF2_SALT_BYTES)
            session.add(
                totp_entity.TotpRecoveryCode(
                    uuid=str(uuid_lib.uuid4()),
                    account_uuid=account_uuid,
                    code_id=f'{credential_uuid[:8]}-{index:02d}',
                    salt=salt,
                    digest=_pbkdf2_digest(code_value, salt),
                    algorithm=_RECOVERY_CODE_ALGORITHM,
                    iterations=_PBKDF2_ITERATIONS,
                )
            )

    async def disable(self, account_uuid: str, *, code: str | None = None) -> bool:
        """Disable TOTP. A live TOTP code or a recovery code is required."""

        credential = await self.get_credential(account_uuid)
        if credential is None or credential.confirmed_at is None:
            raise TotpNotEnrolledError('TOTP is not enabled for this Account')
        if not code:
            raise TotpInvalidCodeError('A TOTP or recovery code is required to disable TOTP')
        if not await self.verify_code(account_uuid, code, allow_recovery=True):
            raise TotpInvalidCodeError('Invalid TOTP code')

        now = _utc_now_naive()
        async with self._session_factory()() as session:
            async with session.begin():
                await session.execute(
                    sqlalchemy.update(totp_entity.TotpCredential)
                    .where(totp_entity.TotpCredential.account_uuid == account_uuid)
                    .values(disabled_at=now)
                )
                await session.execute(
                    sqlalchemy.delete(totp_entity.TotpRecoveryCode).where(
                        totp_entity.TotpRecoveryCode.account_uuid == account_uuid
                    )
                )
        return True

    # ------------------------------------------------------------------
    # owner/admin oversight
    # ------------------------------------------------------------------
    async def list_account_states(
        self,
        *,
        account_uuids: typing.Sequence[str],
    ) -> list[dict[str, typing.Any]]:
        """Second-factor state for the Accounts a Workspace owner/admin may see.

        Oversight belongs to the Workspace, so the caller supplies the member
        Account UUIDs of its own Workspace: an owner/admin must never observe or
        manage another tenant's Accounts.

        Only state is returned: no secret and no recovery-code material.
        """

        credential = totp_entity.TotpCredential
        unused_codes = (
            sqlalchemy.select(
                totp_entity.TotpRecoveryCode.account_uuid.label('account_uuid'),
                sqlalchemy.func.count().label('unused'),
            )
            .where(totp_entity.TotpRecoveryCode.used_at.is_(None))
            .group_by(totp_entity.TotpRecoveryCode.account_uuid)
            .subquery()
        )
        statement = (
            sqlalchemy.select(
                user.User.uuid,
                user.User.user,
                user.User.status,
                credential.confirmed_at,
                credential.last_used_at,
                sqlalchemy.func.coalesce(unused_codes.c.unused, 0),
            )
            .where(user.User.uuid.in_(tuple(account_uuids)))
            .outerjoin(
                credential,
                sqlalchemy.and_(
                    credential.account_uuid == user.User.uuid,
                    credential.disabled_at.is_(None),
                ),
            )
            .outerjoin(unused_codes, unused_codes.c.account_uuid == user.User.uuid)
            .order_by(user.User.user)
        )
        async with self._session_factory()() as session:
            rows = (await session.execute(statement)).all()

        return [
            {
                'account_uuid': row[0],
                'user': row[1],
                'status': row[2],
                'enabled': row[3] is not None,
                'last_used_at': row[4].isoformat() if row[4] else None,
                'recovery_codes_remaining': int(row[5] or 0),
            }
            for row in rows
        ]

    async def revoke_for_account(self, account_uuid: str) -> bool:
        """Owner/admin override: retire an Account's factor without its code.

        Used when the operator has lost the authenticator and every recovery
        code. The credential is soft-disabled so the action stays auditable and
        outstanding recovery codes are destroyed.
        """

        now = _utc_now_naive()
        async with self._session_factory()() as session:
            async with session.begin():
                result = await session.execute(
                    sqlalchemy.update(totp_entity.TotpCredential)
                    .where(
                        totp_entity.TotpCredential.account_uuid == account_uuid,
                        totp_entity.TotpCredential.disabled_at.is_(None),
                    )
                    .values(disabled_at=now)
                )
                await session.execute(
                    sqlalchemy.delete(totp_entity.TotpRecoveryCode).where(
                        totp_entity.TotpRecoveryCode.account_uuid == account_uuid
                    )
                )
        return bool(result.rowcount)

    # ------------------------------------------------------------------
    # verification
    # ------------------------------------------------------------------
    def _decrypt_secret(self, ciphertext: str, key_version: int) -> bytes:
        try:
            return self._fernet(key_version).decrypt(ciphertext.encode('ascii'))
        except InvalidToken as exc:
            raise TotpError('Stored TOTP secret cannot be decrypted with the instance key') from exc

    def _verify_counter(self, credential: totp_entity.TotpCredential, code: str) -> int:
        """Constant-time TOTP verification with a +/- one step drift window."""

        normalized = _normalize_code(code)
        if credential.algorithm.upper() != 'SHA1':
            raise TotpError('Only SHA1 TOTP is supported')
        if len(normalized) != credential.digits:
            raise TotpInvalidCodeError('Invalid TOTP code')

        # The stored plaintext is the base32 secret; HMAC needs the raw key.
        encoded_secret = self._decrypt_secret(credential.secret_ciphertext, credential.key_version)
        secret_bytes = _decode_secret(encoded_secret.decode('ascii'))
        current = _totp_counter(credential.period)
        for candidate in (current, current - 1, current + 1):
            if credential.last_used_counter is not None and candidate <= credential.last_used_counter:
                # Reject replays inside an already-consumed window.
                continue
            if hmac.compare_digest(_hotp(secret_bytes, candidate, credential.digits), normalized):
                return candidate
        raise TotpInvalidCodeError('Invalid TOTP code')

    async def verify_code(
        self,
        account_uuid: str,
        code: str,
        *,
        allow_recovery: bool = False,
        consume_counter: bool = True,
    ) -> bool:
        """Verify a TOTP code, optionally falling back to a recovery code."""

        credential = await self.get_credential(account_uuid)
        if credential is None or credential.confirmed_at is None:
            raise TotpNotEnrolledError('TOTP is not enabled for this Account')

        try:
            counter = self._verify_counter(credential, code)
        except TotpInvalidCodeError:
            if not allow_recovery:
                raise
            if await self.use_recovery_code(account_uuid, code):
                return True
            raise

        if consume_counter:
            now = _utc_now_naive()
            async with self._session_factory()() as session:
                async with session.begin():
                    await session.execute(
                        sqlalchemy.update(totp_entity.TotpCredential)
                        .where(
                            totp_entity.TotpCredential.uuid == credential.uuid,
                            sqlalchemy.or_(
                                totp_entity.TotpCredential.last_used_counter.is_(None),
                                totp_entity.TotpCredential.last_used_counter < counter,
                            ),
                        )
                        .values(last_used_counter=counter, last_used_at=now)
                    )
        return True

    async def use_recovery_code(self, account_uuid: str, code: str) -> bool:
        """Consume one unused recovery code. The code is never logged."""

        normalized = _normalize_code(code)
        if len(normalized) < 16:
            return False

        async with self._session_factory()() as session:
            rows = list(
                await session.scalars(
                    sqlalchemy.select(totp_entity.TotpRecoveryCode).where(
                        totp_entity.TotpRecoveryCode.account_uuid == account_uuid,
                        totp_entity.TotpRecoveryCode.used_at.is_(None),
                    )
                )
            )
            # Compare every stored digest in constant time and only remember
            # whether a match happened: an early `break` leaks, through response
            # timing, how many codes were probed before the match was found.
            matched_id: int | None = None
            for row in rows:
                if hmac.compare_digest(_pbkdf2_digest(normalized, row.salt, row.iterations), row.digest):
                    matched_id = row.id
            if matched_id is None:
                return False

            # Single-use: the guard on used_at keeps concurrent spends from
            # both succeeding.
            result = await session.execute(
                sqlalchemy.update(totp_entity.TotpRecoveryCode)
                .where(
                    totp_entity.TotpRecoveryCode.id == matched_id,
                    totp_entity.TotpRecoveryCode.used_at.is_(None),
                )
                .values(used_at=_utc_now_naive())
            )
            await session.commit()
        return bool(result.rowcount)

    async def count_unused_recovery_codes(self, account_uuid: str) -> int:
        statement = (
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(totp_entity.TotpRecoveryCode)
            .where(
                totp_entity.TotpRecoveryCode.account_uuid == account_uuid,
                totp_entity.TotpRecoveryCode.used_at.is_(None),
            )
        )
        async with self._session_factory()() as session:
            return int(await session.scalar(statement) or 0)

    async def get_account(self, account_uuid: str) -> user.User | None:
        statement = sqlalchemy.select(user.User).where(user.User.uuid == account_uuid)
        async with self._session_factory()() as session:
            return await session.scalar(statement)


__all__ = [
    'TotpAlreadyEnrolledError',
    'TotpChallengeData',
    'TotpChallengeError',
    'TotpEnrollment',
    'TotpError',
    'TotpInvalidCodeError',
    'TotpNotEnrolledError',
    'TotpRecoveryCodes',
    'TotpRequiredError',
    'TotpService',
    'build_totp_uri',
    'render_totp_qr_data_url',
]
