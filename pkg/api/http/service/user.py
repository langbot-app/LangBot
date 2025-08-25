from __future__ import annotations

import sqlalchemy
import argon2
import jwt
import datetime

from ....core import app
from ....entity.persistence import user
from ....utils import constants


class UserService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def is_initialized(self) -> bool:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(user.User).limit(1))

        result_list = result.all()
        return result_list is not None and len(result_list) > 0

    async def create_user(self, user_email: str, password: str) -> None:
        ph = argon2.PasswordHasher()

        hashed_password = ph.hash(password)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(user.User).values(user=user_email, password=hashed_password)
        )

    async def get_user_by_email(self, user_email: str) -> user.User | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(user.User).where(user.User.user == user_email)
        )

        result_list = result.all()
        return result_list[0] if result_list is not None and len(result_list) > 0 else None

    async def authenticate(self, user_email: str, password: str) -> str | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(user.User).where(user.User.user == user_email)
        )

        result_list = result.all()

        if result_list is None or len(result_list) == 0:
            raise ValueError('用户不存在')

        user_obj = result_list[0]

        ph = argon2.PasswordHasher()

        ph.verify(user_obj.password, password)

        return await self.generate_jwt_token(user_email)

    async def generate_jwt_token(self, user_email: str) -> str:
        jwt_secret = self.ap.instance_config.data['system']['jwt']['secret']
        jwt_expire = self.ap.instance_config.data['system']['jwt']['expire']

        payload = {
            'user': user_email,
            'iss': 'LangBot-' + constants.edition,
            'exp': datetime.datetime.now() + datetime.timedelta(seconds=jwt_expire),
        }

        return jwt.encode(payload, jwt_secret, algorithm='HS256')

    async def verify_jwt_token(self, token: str) -> str:
        jwt_secret = self.ap.instance_config.data['system']['jwt']['secret']

        return jwt.decode(token, jwt_secret, algorithms=['HS256'])['user']

    async def reset_password(self, user_email: str, new_password: str) -> None:
        ph = argon2.PasswordHasher()

        hashed_password = ph.hash(new_password)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(user.User).where(user.User.user == user_email).values(password=hashed_password)
        )

    async def change_password(self, user_email: str, current_password: str, new_password: str) -> None:
        ph = argon2.PasswordHasher()

        user_obj = await self.get_user_by_email(user_email)
        if user_obj is None:
            raise ValueError('User not found')

        ph.verify(user_obj.password, current_password)

        hashed_password = ph.hash(new_password)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(user.User).where(user.User.user == user_email).values(password=hashed_password)
        )
