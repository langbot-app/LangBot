import quart
import argon2
import asyncio
from urllib.parse import parse_qs, urlsplit

from .. import group
from .....entity.errors import account as account_errors
from ...context import RequestContext
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
            json_data = await quart.request.json

            try:
                token = await self.ap.user_service.authenticate(json_data['user'], json_data['password'])
            except argon2.exceptions.VerifyMismatchError:
                return self.fail(1, 'Invalid username or password')
            except ValueError as e:
                return self.fail(1, str(e))

            return self.success(data={'token': token})

        @self.route('/check-token', methods=['GET'], auth_type=group.AuthType.ACCOUNT_TOKEN)
        async def _(user_email: str) -> str:
            token = await self.ap.user_service.generate_jwt_token(user_email)

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

            if not code:
                return self.fail(1, 'Missing authorization code')
            if not state:
                return self.fail(1, 'Missing state parameter')

            try:
                await self.ap.user_service.consume_space_oauth_state(state, 'login')
                # Exchange code for tokens
                token_data = await self.ap.space_service.exchange_oauth_code(code)
                access_token = token_data.get('access_token')
                refresh_token = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 0)

                if not access_token:
                    return self.fail(1, 'Failed to get access token from Space')

                # Authenticate and create/update local user
                jwt_token, user_obj = await self.ap.user_service.authenticate_space_user(
                    access_token, refresh_token, expires_in
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
                return self.fail(3, str(e))
            except ValueError:
                self.ap.logger.exception('Space OAuth callback failed')
                return self.fail(1, 'Space OAuth failed')
            except Exception:
                raise

        @self.route('/info', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            """Get current user information including account type"""
            user_obj = await self.ap.user_service.get_user_by_email(user_email)

            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            return self.success(
                data={
                    'account_uuid': user_obj.uuid,
                    'user': user_obj.user,
                    'account_type': user_obj.account_type,
                    'has_password': bool(user_obj.password and user_obj.password.strip()),
                }
            )

        @self.route('/space-credits', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            """Get Space credits balance for current user"""
            credits = await self.ap.space_service.get_credits(user_email)
            return self.success(data={'credits': credits})

        @self.route('/account-info', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Return instance login capabilities without disclosing an account."""
            if not await self.ap.user_service.is_initialized():
                return self.success(data={'initialized': False})

            return self.success(
                data={
                    'initialized': True,
                    # Login is selected per account in a multi-user instance. A public
                    # bootstrap endpoint must never project one user's authentication
                    # methods onto every other user or disclose that user's state.
                    'password_login_enabled': True,
                    'space_login_enabled': True,
                }
            )

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
            except ValueError:
                self.ap.logger.exception('Space account binding failed')
                return self.http_status(400, -1, 'Space account binding failed')
            except Exception:
                raise
