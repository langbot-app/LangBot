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
                return self.fail(1, '系统已初始化')

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
                return self.fail(1, '用户名或密码错误')

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
                return self.http_status(400, -1, 'system not initialized')

            user_obj = await self.ap.user_service.get_user_by_email(user_email)

            if user_obj is None:
                return self.http_status(400, -1, 'user not found')

            if recovery_key != self.ap.instance_config.data['system']['recovery_key']:
                return self.http_status(403, -1, 'invalid recovery key')

            await self.ap.user_service.reset_password(user_email, new_password)

            return self.success(data={'user': user_email})
