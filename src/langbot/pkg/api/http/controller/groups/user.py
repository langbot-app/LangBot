import quart
import argon2
import asyncio
import datetime
import uuid
from urllib.parse import parse_qs, urlsplit

from .. import group
from .....entity.errors import account as account_errors
from ...context import RequestContext
from .....cloud.launch import SpaceLaunchError
from ...service.user import ControlPlaneDirectoryRequiredError, PublicRegistrationClosedError


@group.group_class('user', '/api/v1/user')
class UserRouterGroup(group.RouterGroup):
    @staticmethod
    def _origin(value: str) -> tuple[str, str, int | None] | None:
        parsed = urlsplit(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            return None
        return parsed.scheme, parsed.hostname.casefold(), parsed.port

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
            raise ValueError('Invalid Space login redirect_uri')

        redirect_origin = self._origin(redirect_uri)
        api_config = self.ap.instance_config.data.get('api', {})
        trusted_origins = {
            self._origin(str(api_config.get(config_key, '') or '').strip())
            for config_key in ('webui_url', 'webhook_prefix')
        }
        trusted_origins.discard(None)
        if redirect_origin not in trusted_origins:
            raise ValueError('Untrusted redirect_uri origin')
        return redirect_uri

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

            if recovery_key != self.ap.instance_config.data['system']['recovery_key']:
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

            try:
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
                )
                access_token = token_data.get('access_token')
                refresh_token = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 0)

                if not access_token:
                    return self.fail(1, 'Failed to get access token from Space')

                # Authenticate and create/update local user
                jwt_token, user_obj = await self.ap.user_service.authenticate_space_user(
                    access_token, refresh_token, expires_in
                )

                if launch_workspace_uuid:
                    try:
                        access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
                            user_obj.uuid,
                            launch_workspace_uuid,
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

            if not code:
                return self.http_status(400, -1, 'Missing authorization code')

            if not state:
                return self.http_status(400, -1, 'Missing state parameter')

            try:
                user_obj = await self.ap.user_service.consume_space_oauth_state(state, 'bind')
            except Exception:
                return self.http_status(401, -1, 'Invalid or expired state')
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            if user_obj.account_type != 'local':
                return self.http_status(400, -1, 'Only local accounts can bind to Space')

            try:
                updated_user = await self.ap.user_service.bind_space_account(user_obj.user, code)
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
                return self.http_status(400, -1, 'Space account binding failed')
            except Exception:
                raise

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
