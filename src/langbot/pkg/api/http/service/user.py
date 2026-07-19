from __future__ import annotations

import sqlalchemy
import argon2
import jwt
import datetime
import typing
import asyncio
import hashlib
import secrets
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....entity.persistence import user
from ....utils import constants
from ....entity.errors import account as account_errors
from ....workspace.collaboration import normalize_email
from ..authz import Permission, permissions_for_role

if typing.TYPE_CHECKING:
    from ....core.app import Application


class AccountExistsLoginRequiredError(ValueError):
    code = 'account_exists_login_required'


class PublicRegistrationClosedError(ValueError):
    code = 'registration_closed'


class ControlPlaneDirectoryRequiredError(PublicRegistrationClosedError):
    code = 'control_plane_required'


class AccountDisabledError(ValueError):
    code = 'account_disabled'


class UserService:
    ap: Application
    _create_user_lock: asyncio.Lock

    def __init__(self, ap: Application) -> None:
        self.ap = ap
        self._create_user_lock = asyncio.Lock()
        self._password_hash_lock = asyncio.Semaphore(1)
        self._space_oauth_state_lock = asyncio.Lock()
        self._space_oauth_states: dict[str, tuple[str, str | None, float]] = {}

    @staticmethod
    def _space_oauth_state_digest(state: str) -> str:
        return hashlib.sha256(state.encode('utf-8')).hexdigest()

    async def issue_space_oauth_state(
        self,
        purpose: typing.Literal['login', 'bind'],
        *,
        account_uuid: str | None = None,
        ttl_seconds: int = 600,
    ) -> str:
        """Issue an opaque, single-use OAuth state without exposing a JWT."""
        if purpose == 'bind' and not account_uuid:
            raise ValueError('An Account is required for Space binding')
        if purpose == 'login' and account_uuid is not None:
            raise ValueError('Login state cannot be bound to an Account')
        if ttl_seconds <= 0:
            raise ValueError('OAuth state lifetime must be positive')

        raw_state = secrets.token_urlsafe(32)
        digest = self._space_oauth_state_digest(raw_state)
        expires_at = time.monotonic() + min(ttl_seconds, 600)
        async with self._space_oauth_state_lock:
            now = time.monotonic()
            self._space_oauth_states = {key: value for key, value in self._space_oauth_states.items() if value[2] > now}
            if len(self._space_oauth_states) >= 4096:
                oldest = min(self._space_oauth_states, key=lambda key: self._space_oauth_states[key][2])
                self._space_oauth_states.pop(oldest, None)
            self._space_oauth_states[digest] = (purpose, account_uuid, expires_at)
        return raw_state

    async def consume_space_oauth_state(
        self,
        raw_state: str,
        purpose: typing.Literal['login', 'bind'],
    ) -> user.User | None:
        """Atomically consume OAuth state and resolve its active bind Account."""
        if not isinstance(raw_state, str) or not raw_state:
            raise ValueError('Invalid or expired OAuth state')
        digest = self._space_oauth_state_digest(raw_state)
        async with self._space_oauth_state_lock:
            entry = self._space_oauth_states.pop(digest, None)
        if entry is None or entry[0] != purpose or entry[2] <= time.monotonic():
            raise ValueError('Invalid or expired OAuth state')
        if purpose == 'login':
            return None

        account_uuid = entry[1]
        account = await self.get_user_by_uuid(account_uuid or '')
        if account is None:
            raise ValueError('Invalid or expired OAuth state')
        self._require_active_account(account)
        return account

    async def _hash_password(self, password: str) -> str:
        async with self._password_hash_lock:
            return await asyncio.to_thread(argon2.PasswordHasher().hash, password)

    def _require_local_directory(self) -> None:
        workspace_service = getattr(self.ap, 'workspace_service', None)
        if workspace_service is not None and workspace_service.policy.multi_workspace_enabled:
            raise ControlPlaneDirectoryRequiredError(
                'Cloud Accounts and directory changes are managed by the SaaS control plane'
            )

    async def _verify_password(self, hashed_password: str, password: str) -> None:
        async with self._password_hash_lock:
            await asyncio.to_thread(argon2.PasswordHasher().verify, hashed_password, password)

    async def _update_space_provider_for_account(self, account: typing.Any, api_key: str) -> None:
        """Refresh the OSS Workspace Space provider without guessing a SaaS Workspace.

        Space OAuth credentials belong to an Account, while model-provider secrets
        belong to a Workspace. Community edition has one unambiguous Workspace, so
        the historical automatic refresh remains available to members allowed to
        manage provider secrets. In multi-Workspace SaaS mode the OAuth callback has
        no trusted Workspace selector; the closed control plane or an explicit
        Workspace settings action must perform that linkage instead.
        """

        workspace_service = getattr(self.ap, 'workspace_service', None)
        collaboration_service = getattr(self.ap, 'workspace_collaboration_service', None)
        account_uuid = getattr(account, 'uuid', None)
        if workspace_service is None or collaboration_service is None or not isinstance(account_uuid, str):
            # Never turn a missing tenant kernel into a global secret mutation.
            return
        if workspace_service.policy.multi_workspace_enabled:
            return

        accesses = await collaboration_service.list_account_workspaces(account_uuid)
        if len(accesses) != 1:
            return
        access = accesses[0]
        if Permission.PROVIDER_SECRET_MANAGE.value not in permissions_for_role(access.membership.role):
            return
        await self.ap.provider_service.update_space_model_provider_api_keys(
            access.workspace.uuid,
            api_key,
        )

    async def is_initialized(self) -> bool:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(user.User).limit(1))

        result_list = result.all()
        return result_list is not None and len(result_list) > 0

    def _session_factory(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(self.ap.persistence_mgr.get_db_engine(), expire_on_commit=False)

    def _jwt_identity(self) -> tuple[str, str]:
        workspace_service = getattr(self.ap, 'workspace_service', None)
        instance_uuid = str(getattr(workspace_service, 'instance_uuid', '') or constants.instance_id).strip()
        # UserService is constructed only after config/bootstrap in production.
        # The fallback keeps lightweight isolated unit tests deterministic.
        if not instance_uuid:
            instance_uuid = 'uninitialized-test-instance'
        return 'langbot-core', f'langbot-instance:{instance_uuid}'

    def _legacy_local_tokens_allowed(self) -> bool:
        workspace_service = getattr(self.ap, 'workspace_service', None)
        policy = getattr(workspace_service, 'policy', None)
        return getattr(policy, 'multi_workspace_enabled', False) is not True

    async def create_user(self, user_email: str, password: str) -> None:
        """Create the first local Account and Workspace owner atomically."""

        await self.create_initial_account(user_email, password)

    async def create_initial_account(self, user_email: str, password: str) -> user.User:
        self._require_local_directory()
        normalized_email = normalize_email(user_email)
        hashed_password = await self._hash_password(password)

        async with self._create_user_lock:
            async with self._session_factory()() as session:
                async with session.begin():
                    existing_count = int(
                        (await session.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(user.User))) or 0
                    )
                    if existing_count:
                        raise PublicRegistrationClosedError('System already initialized')
                    account = self._new_account(normalized_email, hashed_password)
                    session.add(account)
                    await session.flush()
                    await self.ap.workspace_service.bootstrap_local_account(account.uuid, session=session)
                    return account

    async def register_invited_account(
        self,
        invitation_token: str,
        user_email: str,
        password: str,
    ) -> tuple[user.User, typing.Any, str]:
        """Create an invited Account and accept its Membership in one transaction."""

        self._require_local_directory()
        normalized_email = normalize_email(user_email)
        invitation, _ = await self.ap.workspace_collaboration_service.inspect_invitation(invitation_token)
        if invitation.normalized_email != normalized_email:
            from ....workspace.collaboration import InvitationEmailMismatchError

            raise InvitationEmailMismatchError('Invitation email does not match the Account')
        hashed_password = await self._hash_password(password)

        async with self._create_user_lock:
            async with self._session_factory()() as session:
                async with session.begin():
                    existing = await session.scalar(
                        sqlalchemy.select(user.User).where(user.User.normalized_email == normalized_email)
                    )
                    if existing is not None:
                        raise AccountExistsLoginRequiredError('An Account already exists for this email')
                    account = self._new_account(normalized_email, hashed_password)
                    session.add(account)
                    await session.flush()
                    membership = await self.ap.workspace_collaboration_service.accept_invitation(
                        invitation_token,
                        account.uuid,
                        session=session,
                    )
                token = await self.generate_jwt_token(account)
                return account, membership, token

    def _new_account(self, normalized_email: str, hashed_password: str) -> user.User:
        return user.User(
            uuid=str(uuid.uuid4()),
            user=normalized_email,
            normalized_email=normalized_email,
            password=hashed_password,
            account_type='local',
            status=user.AccountStatus.ACTIVE.value,
            source=user.AccountSource.LOCAL.value,
            projection_revision=0,
        )

    async def get_user_by_email(self, user_email: str) -> user.User | None:
        normalized_email = user_email.strip().casefold()
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(user.User).where(user.User.normalized_email == normalized_email)
        )

        result_list = result.all()
        return result_list[0] if result_list is not None and len(result_list) > 0 else None

    async def get_user_by_uuid(self, account_uuid: str) -> user.User | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(user.User).where(user.User.uuid == account_uuid)
        )
        return result.first()

    async def get_user_by_space_account_uuid(self, space_account_uuid: str) -> user.User | None:
        """Get user by Space account UUID"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(user.User).where(user.User.space_account_uuid == space_account_uuid)
        )

        result_list = result.all()
        return result_list[0] if result_list is not None and len(result_list) > 0 else None

    async def authenticate(self, user_email: str, password: str) -> str | None:
        user_obj = await self.get_user_by_email(user_email)
        if user_obj is None:
            raise ValueError('用户不存在')
        self._require_active_account(user_obj)

        # Check if this user has a local password set
        if not user_obj.password:
            raise ValueError('请使用 Space 账户登录')

        await self._verify_password(user_obj.password, password)

        return await self.generate_jwt_token(user_obj)

    async def generate_jwt_token(self, account: user.User | str) -> str:
        jwt_secret = self.ap.instance_config.data['system']['jwt']['secret']
        jwt_expire = self.ap.instance_config.data['system']['jwt']['expire']

        account_obj: user.User | None = account if not isinstance(account, str) and hasattr(account, 'user') else None
        user_email = account_obj.user if account_obj is not None else account
        if account_obj is None and hasattr(self.ap, 'persistence_mgr'):
            try:
                account_obj = await self.get_user_by_email(user_email)
            except (AttributeError, TypeError):
                # Lightweight unit-test and bootstrap callers may not have persistence wired.
                account_obj = None

        payload = {
            'user': user_email,
            'iss': self._jwt_identity()[0],
            'aud': self._jwt_identity()[1],
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=jwt_expire),
        }
        if account_obj is not None:
            self._require_active_account(account_obj)
            payload.update(
                {
                    'sub': account_obj.uuid,
                    'account_revision': account_obj.projection_revision,
                }
            )

        return jwt.encode(payload, jwt_secret, algorithm='HS256')

    async def verify_jwt_token(self, token: str) -> str:
        account = await self.get_authenticated_account(token, allow_unresolved_legacy=True)
        if isinstance(account, str):
            return account
        return account.user

    async def get_authenticated_account(
        self,
        token: str,
        *,
        allow_unresolved_legacy: bool = False,
    ) -> user.User | str:
        """Resolve a JWT to an active Account, accepting bounded legacy email tokens."""

        jwt_secret = self.ap.instance_config.data['system']['jwt']['secret']
        issuer, audience = self._jwt_identity()
        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=['HS256'],
                issuer=issuer,
                audience=audience,
                options={'require': ['exp', 'iss', 'aud']},
            )
        except jwt.MissingRequiredClaimError:
            # Preserve one bounded OSS upgrade path for previously issued
            # community tokens. SaaS/Cloud policy never accepts these tokens,
            # and a token carrying a new-style or foreign audience cannot fall
            # back into the legacy decoder.
            unverified = jwt.decode(token, options={'verify_signature': False})
            if (
                not self._legacy_local_tokens_allowed()
                or 'aud' in unverified
                or unverified.get('iss') != 'LangBot-community'
            ):
                raise
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=['HS256'],
                options={'require': ['exp'], 'verify_aud': False, 'verify_iss': False},
            )
        account_obj: user.User | None = None
        account_uuid = payload.get('sub')
        if isinstance(account_uuid, str) and account_uuid:
            try:
                account_obj = await self.get_user_by_uuid(account_uuid)
            except AttributeError:
                account_obj = None
        if account_obj is None:
            legacy_email = payload.get('user')
            if not isinstance(legacy_email, str) or not legacy_email:
                raise ValueError('JWT Account identity is missing')
            try:
                account_obj = await self.get_user_by_email(legacy_email)
            except AttributeError:
                account_obj = None
            if account_obj is None and allow_unresolved_legacy:
                return legacy_email
        if account_obj is None:
            raise ValueError('Account not found')
        self._require_active_account(account_obj)
        token_revision = payload.get('account_revision')
        if token_revision is not None and int(token_revision) != account_obj.projection_revision:
            raise ValueError('Account token revision is stale')
        return account_obj

    @staticmethod
    def _require_active_account(account: user.User) -> None:
        status = getattr(account, 'status', user.AccountStatus.ACTIVE.value)
        if isinstance(status, str) and status != user.AccountStatus.ACTIVE.value:
            raise AccountDisabledError('Account is disabled')

    async def reset_password(self, user_email: str, new_password: str) -> None:
        hashed_password = await self._hash_password(new_password)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(user.User)
            .where(user.User.normalized_email == normalize_email(user_email))
            .values(password=hashed_password)
        )

    async def change_password(self, user_email: str, current_password: str, new_password: str) -> None:
        user_obj = await self.get_user_by_email(user_email)
        if user_obj is None:
            raise ValueError('User not found')

        if not user_obj.password:
            raise ValueError('No local password set, please set a password first')

        await self._verify_password(user_obj.password, current_password)

        hashed_password = await self._hash_password(new_password)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(user.User)
            .where(user.User.normalized_email == normalize_email(user_email))
            .values(password=hashed_password)
        )

    # Space user management

    async def create_or_update_space_user(
        self,
        space_account_uuid: str,
        email: str,
        access_token: str,
        refresh_token: str,
        api_key: str,
        expires_in: int = 0,
    ) -> user.User:
        """Create or update a Space user account (only if system not initialized or user exists)"""
        self._require_local_directory()
        expires_at = datetime.datetime.now() + datetime.timedelta(seconds=expires_in) if expires_in > 0 else None

        async with self._create_user_lock:
            # Check if user with this Space UUID already exists
            existing_user = await self.get_user_by_space_account_uuid(space_account_uuid)

            if existing_user:
                # Update existing user's tokens
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(user.User)
                    .where(user.User.space_account_uuid == space_account_uuid)
                    .values(
                        space_access_token=access_token,
                        space_refresh_token=refresh_token,
                        space_api_key=api_key,
                        space_access_token_expires_at=expires_at,
                    )
                )
                await self._update_space_provider_for_account(existing_user, api_key)
                return await self.get_user_by_space_account_uuid(space_account_uuid)

            # Check if user with same email exists
            existing_email_user = await self.get_user_by_email(email)
            if existing_email_user:
                # Email is display/contact identity, not an OAuth subject. An
                # unknown Space subject must never take over an existing local
                # Account merely by presenting the same email. The Account
                # owner must first authenticate locally and use the explicit,
                # account-bound bind flow.
                raise account_errors.AccountEmailMismatchError()

            # Check if system is already initialized
            is_initialized = await self.is_initialized()
            if is_initialized:
                raise account_errors.AccountEmailMismatchError()

            # Create new Space user (first time initialization)
            if hasattr(self.ap.persistence_mgr, 'get_db_engine') and hasattr(self.ap, 'workspace_service'):
                async with self._session_factory()() as session:
                    async with session.begin():
                        account = user.User(
                            uuid=str(uuid.uuid4()),
                            user=normalize_email(email),
                            normalized_email=normalize_email(email),
                            password='',
                            account_type='space',
                            status=user.AccountStatus.ACTIVE.value,
                            source=user.AccountSource.LOCAL.value,
                            projection_revision=0,
                            space_account_uuid=space_account_uuid,
                            space_access_token=access_token,
                            space_refresh_token=refresh_token,
                            space_api_key=api_key,
                            space_access_token_expires_at=expires_at,
                        )
                        session.add(account)
                        await session.flush()
                        await self.ap.workspace_service.bootstrap_local_account(account.uuid, session=session)
            else:
                # Compatibility path for lightweight service tests without a real engine.
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(user.User).values(
                        user=normalize_email(email),
                        normalized_email=normalize_email(email),
                        password='',
                        account_type='space',
                        space_account_uuid=space_account_uuid,
                        space_access_token=access_token,
                        space_refresh_token=refresh_token,
                        space_api_key=api_key,
                        space_access_token_expires_at=expires_at,
                    )
                )
            created_user = await self.get_user_by_space_account_uuid(space_account_uuid)
            if created_user is not None:
                await self._update_space_provider_for_account(created_user, api_key)
            return created_user

    async def authenticate_space_user(
        self, access_token: str, refresh_token: str, expires_in: int = 0
    ) -> typing.Tuple[str, user.User]:
        """Authenticate with Space and return JWT token"""
        # Get user info from Space using raw API (token just obtained, no need to validate)
        user_info = await self.ap.space_service.get_user_info_raw(access_token)

        account = user_info.get('account', {})
        api_key = user_info.get('api_key', '')

        space_account_uuid = account.get('uuid')
        email = account.get('email')

        if not space_account_uuid or not email:
            raise ValueError('Invalid Space user info')

        # Create or update Space user in local database
        user_obj = await self.create_or_update_space_user(
            space_account_uuid=space_account_uuid,
            email=email,
            access_token=access_token,
            refresh_token=refresh_token,
            api_key=api_key,
            expires_in=expires_in,
        )

        # Generate JWT token
        jwt_token = await self.generate_jwt_token(user_obj)

        return jwt_token, user_obj

    async def get_first_user(self) -> user.User | None:
        """Get the first user (for single-user mode)"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(user.User).limit(1))
        result_list = result.all()
        return result_list[0] if result_list else None

    async def set_password(self, user_email: str, new_password: str, current_password: str | None = None) -> None:
        """Set or change password for a user"""
        user_obj = await self.get_user_by_email(user_email)

        if user_obj is None:
            raise ValueError('User not found')

        # If user already has a password, verify current password
        has_password = bool(user_obj.password and user_obj.password.strip())
        if has_password:
            if not current_password:
                raise ValueError('Current password is required')
            await self._verify_password(user_obj.password, current_password)

        hashed_password = await self._hash_password(new_password)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(user.User)
            .where(user.User.normalized_email == normalize_email(user_email))
            .values(password=hashed_password)
        )

    async def bind_space_account(self, user_email: str, code: str) -> user.User:
        """Bind Space account to existing local account"""
        local_account = await self.get_user_by_email(user_email)
        if local_account is None:
            raise ValueError('User not found')
        # Exchange code for tokens
        token_data = await self.ap.space_service.exchange_oauth_code(code)
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 0)

        if not access_token:
            raise ValueError('Failed to get access token from Space')

        expires_at = datetime.datetime.now() + datetime.timedelta(seconds=expires_in) if expires_in > 0 else None

        # Get Space user info (token just obtained, use raw API)
        user_info = await self.ap.space_service.get_user_info_raw(access_token)
        account = user_info.get('account', {})
        api_key = user_info.get('api_key', '')

        space_account_uuid = account.get('uuid')
        space_email = account.get('email')

        if not space_account_uuid or not space_email:
            raise ValueError('Invalid Space user info')

        # Check if this Space account is already bound to another user
        existing_space_user = await self.get_user_by_space_account_uuid(space_account_uuid)
        if existing_space_user and existing_space_user.normalized_email != normalize_email(user_email):
            raise ValueError('This Space account is already bound to another user')

        # Update local account to Space account
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(user.User)
            .where(user.User.normalized_email == normalize_email(user_email))
            .values(
                user=normalize_email(space_email),  # Update email to Space email
                normalized_email=normalize_email(space_email),
                account_type='space',
                space_account_uuid=space_account_uuid,
                space_access_token=access_token,
                space_refresh_token=refresh_token,
                space_api_key=api_key,
                space_access_token_expires_at=expires_at,
            )
        )

        # Update Space model provider API keys
        await self._update_space_provider_for_account(local_account, api_key)

        return await self.get_user_by_email(space_email)
