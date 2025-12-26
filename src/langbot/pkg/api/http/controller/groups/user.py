import quart
import argon2
import asyncio

from .. import group


@group.group_class('user', '/api/v1/user')
class UserRouterGroup(group.RouterGroup):
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

            await self.ap.user_service.create_user(user_email, password)

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

        @self.route('/check-token', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
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
            allow_change_password = self.ap.instance_config.data.get('system', {}).get('allow_change_password', True)
            if not allow_change_password:
                return self.http_status(403, -1, 'Password change is disabled')

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
            state = quart.request.args.get('state', '')

            if not redirect_uri:
                return self.fail(1, 'Missing redirect_uri parameter')

            try:
                authorize_url = self.ap.user_service.get_space_oauth_authorize_url(redirect_uri, state)
                return self.success(data={'authorize_url': authorize_url})
            except Exception as e:
                return self.fail(1, str(e))

        @self.route('/space/callback', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Handle OAuth callback - exchange code for tokens and authenticate"""
            json_data = await quart.request.json
            code = json_data.get('code')

            if not code:
                return self.fail(1, 'Missing authorization code')

            try:
                # Exchange code for tokens
                token_data = await self.ap.user_service.exchange_space_oauth_code(code)
                access_token = token_data.get('access_token')
                refresh_token = token_data.get('refresh_token')

                if not access_token:
                    return self.fail(1, 'Failed to get access token from Space')

                # Authenticate and create/update local user
                jwt_token, user_obj = await self.ap.user_service.authenticate_space_user(access_token, refresh_token)

                return self.success(
                    data={
                        'token': jwt_token,
                        'user': user_obj.user,
                    }
                )
            except ValueError as e:
                return self.fail(1, str(e))
            except Exception as e:
                return self.fail(2, f'OAuth callback failed: {str(e)}')

        @self.route('/info', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            """Get current user information including account type"""
            user_obj = await self.ap.user_service.get_user_by_email(user_email)

            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            return self.success(
                data={
                    'user': user_obj.user,
                    'account_type': user_obj.account_type,
                    'has_password': bool(user_obj.password and user_obj.password.strip()),
                }
            )

        @self.route('/account-info', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            """Get account info for login page (account type and has_password)"""
            if not await self.ap.user_service.is_initialized():
                return self.success(data={'initialized': False})

            user_obj = await self.ap.user_service.get_first_user()
            if user_obj is None:
                return self.success(data={'initialized': False})

            return self.success(
                data={
                    'initialized': True,
                    'account_type': user_obj.account_type,
                    'has_password': bool(user_obj.password and user_obj.password.strip()),
                }
            )

        @self.route('/set-password', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _(user_email: str) -> str:
            """Set password for Space account (first time) or change password"""
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
            json_data = await quart.request.json
            code = json_data.get('code')
            state = json_data.get('state')  # JWT token passed as state

            if not code:
                return self.http_status(400, -1, 'Missing authorization code')

            if not state:
                return self.http_status(400, -1, 'Missing state parameter')

            # Verify state is a valid JWT token
            try:
                user_email = await self.ap.user_service.verify_jwt_token(state)
            except Exception:
                return self.http_status(401, -1, 'Invalid or expired state')

            user_obj = await self.ap.user_service.get_user_by_email(user_email)
            if user_obj is None:
                return self.http_status(404, -1, 'User not found')

            if user_obj.account_type != 'local':
                return self.http_status(400, -1, 'Only local accounts can bind to Space')

            try:
                updated_user = await self.ap.user_service.bind_space_account(user_email, code)
                jwt_token = await self.ap.user_service.generate_jwt_token(updated_user.user)
                return self.success(
                    data={
                        'token': jwt_token,
                        'user': updated_user.user,
                        'account_type': updated_user.account_type,
                    }
                )
            except ValueError as e:
                return self.http_status(400, -1, str(e))
            except Exception as e:
                return self.http_status(500, -1, f'Failed to bind Space account: {str(e)}')
