from __future__ import annotations

import quart
import argon2
import asyncio
import datetime
import hmac
import time
import typing
import uuid
from urllib.parse import parse_qs, urlsplit

from .. import group
from .....entity.errors import account as account_errors
from ...context import RequestContext
from .....cloud.launch import SpaceLaunchError
from ...service.user import ControlPlaneDirectoryRequiredError, PublicRegistrationClosedError

# Fixed-window admission quota for the unauthenticated reset-password endpoint (#2392).
# The admission check and slot bump share ONE synchronous critical section with no await
# points, so concurrent bursts within a single event loop cannot slip past accounting.
# Every admitted attempt consumes quota (regardless of success), which throttles both the
# legacy 24-bit keyspace exhaustion and brute-force on modern high-entropy keys.
# NOTE: this state is process-local; multi-worker deployments need a shared limiter upstream.
_MAX_RESET_ATTEMPTS_PER_WINDOW = 5
_RESET_WINDOW_SECONDS = 15 * 60

_reset_password_state: dict = {'window_started_at': 0.0, 'attempts': 0}


def _admit_reset_attempt(now: float) -> bool:
    """Atomically reserve one reset-password admission slot.

    Must stay await-free: running to completion without suspension makes the
    check-and-increment atomic under the single-threaded event loop.
    """
    st = _reset_password_state
    if now - st['window_started_at'] >= _RESET_WINDOW_SECONDS:
        st['window_started_at'] = now
        st['attempts'] = 0
    if st['attempts'] >= _MAX_RESET_ATTEMPTS_PER_WINDOW:
        return False
    st['attempts'] += 1
    return True


@group.group_class('user', '/api/v1/user')
class UserRouterGroup(group.RouterGroup):
    def _validate_space_redirect_uri(self, redirect_uri: str, *, bind: bool) -> str:
        parsed = urlsplit(redirect_uri)
        if (
            parsed.scheme not in {'http', 'https'}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.path != '/auth/space/callback'
        ):
            raise ValueError('Invalid redirect_uri parameter')

        query = parse_qs(parsed.query, keep_blank_values=True)
        if bind:
            if query != {'mode': ['bind']}:
                raise ValueError('Invalid Space binding redirect_uri')
        elif query:
            raise ValueError('Invalid LangBot Account login redirect_uri')

        return redirect_uri

    def _extract_origin_and_rp_id(self, json_data: dict[str, typing.Any] | None = None) -> tuple[str, str]:
        origin = ''
        if json_data and isinstance(json_data, dict):
            origin = json_data.get('origin', '')
        if not origin:
            origin = quart.request.headers.get('Origin', '')
        if not origin:
            origin = quart.request.headers.get('Referer', '')
        if not origin:
            origin = quart.request.url_root.rstrip('/')

        parsed = urlsplit(origin)
        rp_id = parsed.hostname or 'localhost'
        clean_origin = f'{parsed.scheme}://{parsed.netloc}' if parsed.scheme and parsed.netloc else origin.rstrip('/')
        return clean_origin, rp_id

    async def initialize(self) -> None:
        @self.route('/init', methods=['GET', 'POST'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={'initialized': await self.ap.user_service.is_initialized()})

            if await self.ap.user_service.is_initialized():
                return self.fail(1, 'System already initialized')

            json_data = await quart.request.json

            user_email = json_data['user']
            password = json_data['password']

            try:
                await self.ap.user_service.create_user(user_email, password)
            except ControlPlaneDirectoryRequiredError as exc:
                return self.http_status(409, exc.code, str(exc))
            except PublicRegistrationClosedError:
                return self.http_status(409, 'registration_closed', 'System already initialized')

            return self.success()

        @self.route('/auth', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            if getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'cloud':
                return self.http_status(403, 'password_login_disabled', 'Password login is disabled on LangBot Cloud')
            json_data = await quart.request.json

            try:
                token = await self.ap.user_service.authenticate(json_data['user'], json_data['password'])
            except argon2.exceptions.VerifyMismatchError:
                return self.fail(1, 'Invalid username or password')
            except ValueError as e:
                return self.fail(1, str(e))

            return self.success(data={'token': token})

        @self.route('/check-token', methods=['GET'], auth_type=group.AuthType.ACCOUNT_TOKEN)
        async def _(account) -> str:
            token = await self.ap.user_service.generate_jwt_token(account)

            return self.success(data={'token': token})

        @self.route('/reset-password', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            # Admit (or reject) BEFORE touching the body or any service call (#2392):
            # rejecting requests never reach the slow path, and quota accounting happens
            # synchronously at entry, closing the post-await race of burst requests.
            if not _admit_reset_attempt(time.monotonic()):
                return self.http_status(429, -1, 'Too many attempts, try again later')

            json_data = await quart.request.json

            user_email = json_data['user']
            recovery_key = json_data['recovery_key']
            new_password = json_data['new_password']

            # hard sleep 3s for security
            await asyncio.sleep(3)

            if not await self.ap.user_service.is_initialized():
                return self.http_status(400, -1, 'System not initialized')

            user_obj = await self.ap.user_service.get_user_by_email(user_email)

            if user_obj is None:
                return self.http_status(400, -1, 'User not found')

            stored_key = self.ap.instance_config.data['system']['recovery_key']
            try:
                key_matches = (
                    isinstance(recovery_key, str)
                    and isinstance(stored_key, str)
                    and hmac.compare_digest(recovery_key.encode(), stored_key.encode())
                )
            except UnicodeEncodeError:
                # JSON can contain lone surrogates, which are not valid UTF-8.
                key_matches = False

            if not key_matches:
                return self.http_status(403, -1, 'Invalid recovery key')

            await self.ap.user_service.reset_password(user_email, new_password)

            return self.success(data={'user': user_email})

        @self.route('/change-password', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            # Check if password change is allowed
            allow_modify_login_info = self.ap.instance_config.data.get('system', {}).get(
                'allow_modify_login_info', True
            )
            if not allow_modify_login_info:
                return self.http_status(403, -1, 'Modifying login info is disabled')

            json_data = await quart.request.json

            current_password = json_data['current_password']
            new_password = json_data['new_password']

            try:
                await self.ap.user_service.change_password(user_email, current_password, new_password)
            except argon2.exceptions.VerifyMismatchError:
                return self.http_status(400, -1, 'Current password is incorrect')
            except ValueError as e:
                return self.http_status(400, -1, str(e))

            return self.success(data={'user': user_email})

        # Space OAuth endpoints (redirect flow)

        @self.route('/space/authorize-url', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Get Space OAuth authorization URL for redirect"""
            redirect_uri = quart.request.args.get('redirect_uri', '')

            if not redirect_uri:
                return self.fail(1, 'Missing redirect_uri parameter')
            if 'state' in quart.request.args:
                return self.fail(1, 'Caller-supplied OAuth state is not allowed')

            try:
                redirect_uri = self._validate_space_redirect_uri(redirect_uri, bind=False)
                launch_workspace_uuid = quart.request.args.get('launch_workspace_uuid')
                if launch_workspace_uuid:
                    if not getattr(getattr(self.ap, 'deployment', None), 'multi_workspace_enabled', False):
                        return self.fail(1, 'Space launch requires Cloud mode')
                    try:
                        uuid.UUID(launch_workspace_uuid)
                    except ValueError:
                        return self.fail(1, 'Invalid launch Workspace')
                    state = await self.ap.user_service.issue_space_oauth_state(
                        'login',
                        launch_workspace_uuid=launch_workspace_uuid,
                    )
                else:
                    state = await self.ap.user_service.issue_space_oauth_state('login')
                authorize_url = self.ap.space_service.get_oauth_authorize_url(redirect_uri, state)
                return self.success(data={'authorize_url': authorize_url})
            except ValueError as e:
                return self.fail(1, str(e))

        @self.route('/space/bind-authorize-url', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(request_context: RequestContext) -> str:
            """Issue an account-bound, one-time Space OAuth redirect."""
            redirect_uri = quart.request.args.get('redirect_uri', '')
            if not redirect_uri:
                return self.fail(1, 'Missing redirect_uri parameter')
            if not request_context.account_uuid:
                return self.http_status(403, 'account_required', 'An Account is required')
            try:
                redirect_uri = self._validate_space_redirect_uri(redirect_uri, bind=True)
                state = await self.ap.user_service.issue_space_oauth_state(
                    'bind',
                    account_uuid=request_context.account_uuid,
                )
                authorize_url = self.ap.space_service.get_oauth_authorize_url(redirect_uri, state)
                return self.success(data={'authorize_url': authorize_url})
            except ValueError as e:
                return self.fail(1, str(e))

        @self.route('/space/callback', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Handle OAuth callback - exchange code for tokens and authenticate"""
            json_data = await quart.request.json
            code = json_data.get('code')
            state = json_data.get('state')
            redirect_uri = json_data.get('redirect_uri') or (
                quart.request.url_root.rstrip('/') + '/auth/space/callback'
            )
            launch_assertion = json_data.get('launch_assertion')
            workspace_uuid = json_data.get('workspace_uuid')

            if launch_assertion:
                return await self._handle_space_direct_launch(
                    str(launch_assertion),
                    str(workspace_uuid or '') or None,
                )

            if not code:
                return self.fail(1, 'Missing authorization code')
            if not state:
                return self.fail(1, 'Missing state parameter')
            if not str(code).startswith('v4_'):
                return self.fail(1, 'Unsupported Space OAuth code contract')

            try:
                redirect_uri = self._validate_space_redirect_uri(str(redirect_uri), bind=False)
                consumed_state = await self.ap.user_service.consume_space_oauth_state_details(state, 'login')
                # Exchange code for tokens
                launch_workspace_uuid = consumed_state.launch_workspace_uuid
                workspace_uuids = [launch_workspace_uuid] if launch_workspace_uuid else []
                workspace_created_ats: dict[str, int] = {}
                if not workspace_uuids and getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') != 'cloud':
                    binding = await self.ap.workspace_service.get_execution_binding()
                    workspace_uuids = [binding.workspace_uuid]
                    workspace_created_at = binding.workspace_created_at
                    if workspace_created_at is not None:
                        if workspace_created_at.tzinfo is None:
                            workspace_created_at = workspace_created_at.replace(tzinfo=datetime.UTC)
                        workspace_created_ats[binding.workspace_uuid] = int(workspace_created_at.timestamp())
                token_data = await self.ap.space_service.exchange_oauth_code(
                    code,
                    workspace_uuids,
                    workspace_created_ats,
                    redirect_uri=redirect_uri,
                )
                access_token = token_data.get('access_token')
                refresh_token = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 0)
                cloud_workspace_uuid = token_data.get('cloud_workspace_uuid')

                if not access_token:
                    return self.fail(1, 'Failed to get access token from Space')

                cloud_mode = getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'cloud'
                if cloud_mode and launch_workspace_uuid and launch_workspace_uuid != cloud_workspace_uuid:
                    return self.fail(1, 'Space OAuth Workspace binding mismatch')
                target_workspace_uuid = launch_workspace_uuid or cloud_workspace_uuid
                if cloud_mode:
                    if not target_workspace_uuid:
                        return self.fail(1, 'Space OAuth response is missing the Cloud Workspace binding')
                    await self.ap.directory_projection_service.reconcile_workspaces((target_workspace_uuid,))

                # Authenticate only after the signed, exact Workspace delta has
                # established the Account and membership runtime shadow rows.
                jwt_token, user_obj = await self.ap.user_service.authenticate_space_user(
                    access_token, refresh_token, expires_in
                )

                if target_workspace_uuid:
                    try:
                        access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
                            user_obj.uuid,
                            target_workspace_uuid,
                        )
                    except Exception:
                        self.ap.logger.warning('Rejected Space OAuth launch for unauthorized Workspace')
                        return self.fail(1, 'Space OAuth failed')
                    return self.success(
                        data={
                            'token': jwt_token,
                            'user': user_obj.user,
                            'workspace_uuid': access.workspace.uuid,
                        }
                    )

                return self.success(
                    data={
                        'token': jwt_token,
                        'user': user_obj.user,
                    }
                )
            except ControlPlaneDirectoryRequiredError as e:
                return self.http_status(409, e.code, str(e))
            except account_errors.AccountEmailMismatchError as e:
                return self.fail(getattr(e, 'code', 3), str(e))
            except ValueError:
                self.ap.logger.exception('Space OAuth callback failed')
                return self.fail(1, 'Space OAuth failed')
            except Exception:
                raise

        @self.route('/info', methods=['GET'], auth_type=group.AuthType.ACCOUNT_TOKEN)
        async def _(account) -> str:
            """Get current Account information without re-querying under Workspace RLS."""
            return self.success(
                data={
                    'account_uuid': account.uuid,
                    'user': account.user,
                    'account_type': account.account_type,
                    'has_password': bool(account.password and account.password.strip()),
                }
            )

        @self.route('/space-credits', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(request_context: RequestContext) -> str:
            """Get Space credits using only the selected Workspace owner's credentials."""
            access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
                request_context.account_uuid,
                request_context.workspace_uuid,
            )
            owner = await self.ap.user_service.get_workspace_owner(access.workspace.uuid)
            cloud_mode = getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'cloud'
            owner_has_local_space_credentials = bool(owner and owner.space_account_uuid)
            # Cloud Accounts authenticate through LangBot Account, so every projected
            # Workspace owner is already bound even when this Core has no local OAuth
            # token row (model billing uses the owner's control-plane API key).
            owner_space_bound = cloud_mode or owner_has_local_space_credentials
            if cloud_mode:
                catalog_service = getattr(self.ap, 'cloud_model_catalog_service', None)
                credits = (
                    catalog_service.get_workspace_credits(access.workspace.uuid)
                    if catalog_service is not None
                    else None
                )
            else:
                credits = (
                    await self.ap.space_service.get_credits(owner.user)
                    if owner is not None and owner.space_account_uuid
                    else None
                )
            return self.success(
                data={
                    'credits': credits,
                    'owner_space_bound': owner_space_bound,
                    'is_workspace_owner': access.membership.role == 'owner',
                }
            )

        @self.route('/account-info', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Return instance login capabilities without disclosing an account."""
            if not await self.ap.user_service.is_initialized():
                return self.success(data={'initialized': False})

            capabilities = await self.ap.user_service.get_login_capabilities()
            cloud_mode = getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'cloud'
            if cloud_mode:
                capabilities['password_login_enabled'] = False
            capabilities['authenticated_invitation_acceptance_enabled'] = cloud_mode
            capabilities['invitation_registration_enabled'] = not cloud_mode
            capabilities['passkey_login_enabled'] = True
            capabilities['passkey_supported'] = True
            return self.success(data={'initialized': True, **capabilities})

        @self.route('/set-password', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            """Set password for Space account (first time) or change password"""
            # Check if modifying login info is allowed
            allow_modify_login_info = self.ap.instance_config.data.get('system', {}).get(
                'allow_modify_login_info', True
            )
            if not allow_modify_login_info:
                return self.http_status(403, -1, 'Modifying login info is disabled')

            json_data = await quart.request.json
            new_password = json_data.get('new_password')
            current_password = json_data.get('current_password')

            if not new_password:
                return self.http_status(400, -1, 'New password is required')

            user_obj = await self.ap.user_service.get_user_by_email(user_email)
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            try:
                await self.ap.user_service.set_password(user_email, new_password, current_password)
                return self.success(data={'user': user_email})
            except ValueError as e:
                return self.http_status(400, -1, str(e))
            except argon2.exceptions.VerifyMismatchError:
                return self.http_status(400, -1, 'Current password is incorrect')

        @self.route('/bind-space', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Bind Space account to existing local account"""
            # Check if modifying login info is allowed
            allow_modify_login_info = self.ap.instance_config.data.get('system', {}).get(
                'allow_modify_login_info', True
            )
            if not allow_modify_login_info:
                return self.http_status(403, -1, 'Modifying login info is disabled')

            json_data = await quart.request.json
            code = json_data.get('code')
            state = json_data.get('state')
            redirect_uri = json_data.get('redirect_uri') or (
                quart.request.url_root.rstrip('/') + '/auth/space/callback?mode=bind'
            )

            if not code:
                return self.http_status(400, -1, 'Missing authorization code')

            if not state:
                return self.http_status(400, -1, 'Missing state parameter')
            if not str(code).startswith('v4_'):
                return self.http_status(400, -1, 'Unsupported Space OAuth code contract')

            try:
                user_obj = await self.ap.user_service.consume_space_oauth_state(state, 'bind')
            except Exception:
                return self.http_status(401, -1, 'Invalid or expired state')
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            if user_obj.account_type != 'local':
                return self.http_status(400, -1, 'Only local accounts can bind to Space')

            try:
                redirect_uri = self._validate_space_redirect_uri(str(redirect_uri), bind=True)
                updated_user = await self.ap.user_service.bind_space_account(
                    user_obj.user, code, redirect_uri=redirect_uri
                )
                jwt_token = await self.ap.user_service.generate_jwt_token(updated_user)
                return self.success(
                    data={
                        'token': jwt_token,
                        'user': updated_user.user,
                        'account_type': updated_user.account_type,
                    }
                )
            except account_errors.AccountEmailMismatchError:
                return self.http_status(
                    409,
                    'space_account_email_mismatch',
                    'Bind the LangBot Account with the same email as this local Account',
                )
            except ValueError:
                return self.http_status(400, -1, 'LangBot Account binding failed')
            except Exception:
                raise

        @self.route('/passkey/register/options', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            """Generate WebAuthn registration options for current account."""
            allow_modify_login_info = self.ap.instance_config.data.get('system', {}).get(
                'allow_modify_login_info', True
            )
            if not allow_modify_login_info:
                return self.http_status(403, -1, 'Modifying login info is disabled')

            user_obj = await self.ap.user_service.get_user_by_email(user_email)
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            json_data = (await quart.request.json) or {}
            origin, rp_id = self._extract_origin_and_rp_id(json_data)

            try:
                options, challenge_token = await self.ap.user_service.generate_passkey_registration_options(
                    account_uuid=user_obj.uuid,
                    rp_id=rp_id,
                    origin=origin,
                    rp_name='LangBot',
                )
                return self.success(data={'options': options, 'challenge_token': challenge_token})
            except Exception as e:
                return self.fail(1, str(e))

        @self.route('/passkey/register/verify', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            """Verify WebAuthn registration response and save credential."""
            allow_modify_login_info = self.ap.instance_config.data.get('system', {}).get(
                'allow_modify_login_info', True
            )
            if not allow_modify_login_info:
                return self.http_status(403, -1, 'Modifying login info is disabled')

            user_obj = await self.ap.user_service.get_user_by_email(user_email)
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            json_data = await quart.request.json
            challenge_token = json_data.get('challenge_token')
            credential = json_data.get('credential') or json_data.get('response')
            name = json_data.get('name')

            if not challenge_token or not credential:
                return self.fail(1, 'Missing challenge_token or credential')

            try:
                cred = await self.ap.user_service.verify_and_save_passkey_registration(
                    challenge_token=challenge_token,
                    credential_data=credential,
                    name=name,
                )
                return self.success(
                    data={
                        'uuid': cred.uuid,
                        'name': cred.name,
                        'created_at': cred.created_at.isoformat() if cred.created_at else None,
                    }
                )
            except Exception as e:
                return self.fail(1, str(e))

        @self.route('/passkey/auth/options', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Generate WebAuthn authentication options for passkey login."""
            json_data = (await quart.request.json) or {}
            email = json_data.get('email')
            origin, rp_id = self._extract_origin_and_rp_id(json_data)

            try:
                options, challenge_token = await self.ap.user_service.generate_passkey_authentication_options(
                    rp_id=rp_id,
                    origin=origin,
                    email=email,
                )
                return self.success(data={'options': options, 'challenge_token': challenge_token})
            except Exception as e:
                return self.fail(1, str(e))

        @self.route('/passkey/auth/verify', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Verify WebAuthn authentication response and log in."""
            json_data = await quart.request.json
            challenge_token = json_data.get('challenge_token')
            credential = json_data.get('credential') or json_data.get('response')

            if not challenge_token or not credential:
                return self.fail(1, 'Missing challenge_token or credential')

            try:
                token, user_obj = await self.ap.user_service.verify_passkey_authentication(
                    challenge_token=challenge_token,
                    credential_data=credential,
                )
                return self.success(
                    data={
                        'token': token,
                        'user': user_obj.user,
                    }
                )
            except Exception as e:
                return self.fail(1, str(e))

        @self.route('/passkeys', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            """List registered passkeys for the current user."""
            user_obj = await self.ap.user_service.get_user_by_email(user_email)
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            passkeys = await self.ap.user_service.get_user_passkeys(user_obj.uuid)
            return self.success(
                data=[
                    {
                        'uuid': pk.uuid,
                        'name': pk.name,
                        'aaguid': pk.aaguid,
                        'transports': pk.transports,
                        'backed_up': pk.backed_up,
                        'created_at': pk.created_at.isoformat() if pk.created_at else None,
                        'last_used_at': pk.last_used_at.isoformat() if pk.last_used_at else None,
                    }
                    for pk in passkeys
                ]
            )

        @self.route('/passkey/<passkey_uuid>', methods=['PATCH'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str, passkey_uuid: str) -> str:
            """Rename a registered passkey."""
            allow_modify_login_info = self.ap.instance_config.data.get('system', {}).get(
                'allow_modify_login_info', True
            )
            if not allow_modify_login_info:
                return self.http_status(403, -1, 'Modifying login info is disabled')

            user_obj = await self.ap.user_service.get_user_by_email(user_email)
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            json_data = await quart.request.json
            name = (json_data.get('name') or '').strip()
            if not name:
                return self.fail(1, 'Passkey name cannot be empty')

            updated = await self.ap.user_service.rename_user_passkey(
                account_uuid=user_obj.uuid,
                passkey_uuid=passkey_uuid,
                new_name=name,
            )
            if not updated:
                return self.http_status(404, -1, 'Passkey not found')
            return self.success(data={'uuid': updated.uuid, 'name': updated.name})

        @self.route('/passkey/<passkey_uuid>', methods=['DELETE'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str, passkey_uuid: str) -> str:
            """Delete/revoke a registered passkey."""
            allow_modify_login_info = self.ap.instance_config.data.get('system', {}).get(
                'allow_modify_login_info', True
            )
            if not allow_modify_login_info:
                return self.http_status(403, -1, 'Modifying login info is disabled')

            user_obj = await self.ap.user_service.get_user_by_email(user_email)
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            deleted = await self.ap.user_service.delete_user_passkey(
                account_uuid=user_obj.uuid,
                passkey_uuid=passkey_uuid,
            )
            if not deleted:
                return self.http_status(404, -1, 'Passkey not found')
            return self.success()

    async def _handle_space_direct_launch(
        self,
        launch_assertion: str,
        workspace_uuid: str | None,
    ) -> str:
        try:
            launch = await self.ap.space_launch_service.consume_assertion(
                launch_assertion,
                expected_workspace_uuid=workspace_uuid,
            )
            if launch.get('launch_mode') == 'support_admin':
                token = launch.get('support_admin_token')
                if not token:
                    raise SpaceLaunchError('Support admin launch session was not issued')
                return self.success(
                    data={
                        'token': token,
                        'workspace_uuid': launch['workspace_uuid'],
                        'principal_type': 'support_admin',
                        'actor_account_uuid': launch['actor_account_uuid'],
                    }
                )

            projection_service = self.ap.directory_projection_service
            if projection_service is None:
                raise SpaceLaunchError('Cloud directory projection is unavailable')
            await projection_service.reconcile_workspaces((launch['workspace_uuid'],))
            account = await self.ap.user_service.get_user_by_uuid(launch['account_uuid'])
            if account is None:
                raise SpaceLaunchError('Launch Account is not projected into Core')
            self.ap.user_service._require_active_account(account)
            access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
                account.uuid,
                launch['workspace_uuid'],
            )
            token = await self.ap.user_service.generate_jwt_token(account)
            return self.success(
                data={
                    'token': token,
                    'user': account.user,
                    'workspace_uuid': access.workspace.uuid,
                }
            )
        except SpaceLaunchError:
            self.ap.logger.warning('Rejected Space direct-launch assertion')
            return self.fail(1, 'Space launch failed')
        except Exception:
            self.ap.logger.exception('Space direct launch failed')
            return self.fail(1, 'Space launch failed')
