"""Application operations for principal-bound platform credential setup."""

from __future__ import annotations

from typing import Any
from typing_extensions import NotRequired, TypedDict

from pydantic import Field

from ..authz import Permission
from ..http.service.slack_setup import SlackSetupError, get_slack_setup
from ...platform.credential_setup import CredentialSetupError, get_credential_setup
from .contracts import Input, Operation


class Empty(Input):
    pass


class Session(Input):
    session_id: str = Field(min_length=1)


class SlackStart(Input):
    bot_uuid: str = Field(min_length=1)
    access_token: str = Field(min_length=1)
    refresh_token: str = Field(min_length=1)
    webhook_url: str = ''
    name: str = 'LangBot'
    socket_mode: bool = False
    redirect_url: str = ''


class SessionStarted(TypedDict):
    session_id: str


class QRStarted(SessionStarted):
    qr_url: str
    expire_at: float | None


class WeixinStarted(SessionStarted):
    qr_data_url: str
    expire_at: float | None


class SessionStatus(TypedDict):
    status: str
    error: NotRequired[str | None]
    app_id: NotRequired[str | None]
    app_secret: NotRequired[str | None]
    client_id: NotRequired[str | None]
    client_secret: NotRequired[str | None]
    botid: NotRequired[str | None]
    secret: NotRequired[str | None]
    appid: NotRequired[str | None]
    user_openid: NotRequired[str | None]
    qr_data_url: NotRequired[str | None]
    expire_at: NotRequired[float | None]
    token: NotRequired[str | None]
    base_url: NotRequired[str | None]
    account_id: NotRequired[str | None]
    authorize_url: NotRequired[str | None]
    config: NotRequired[dict[str, Any]]


def _credential_operation(method: str):
    async def execute(ap, context, payload):
        service = get_credential_setup(ap)
        return await getattr(service, method)(request_context=context, **payload.model_dump())

    return execute


async def slack_start(ap, context, payload: SlackStart):
    try:
        return await get_slack_setup(ap).start(context, **payload.model_dump())
    except SlackSetupError as exc:
        raise CredentialSetupError(400, str(exc)) from exc


async def slack_status(ap, context, payload: Session):
    try:
        return get_slack_setup(ap).status(context, payload.session_id)
    except SlackSetupError as exc:
        raise CredentialSetupError(404, 'session_not_found') from exc


async def slack_cancel(ap, context, payload: Session):
    service = get_slack_setup(ap)
    try:
        service.owned(context, payload.session_id)
    except SlackSetupError as exc:
        raise CredentialSetupError(404, 'session_not_found') from exc
    service.discard(payload.session_id)
    return {}


def operations() -> list[Operation]:
    result = []
    for platform in ('lark', 'weixin', 'dingtalk', 'wecombot', 'qqofficial'):
        for action in ('start', 'status', 'cancel'):
            output = (
                (WeixinStarted if platform == 'weixin' else QRStarted)
                if action == 'start'
                else (SessionStatus if action == 'status' else dict)
            )
            result.append(
                Operation(
                    f'platform.setup.{platform}.{action}',
                    Permission.RESOURCE_MANAGE,
                    _credential_operation(f'{platform}_{action}'),
                    Empty if action == 'start' else Session,
                    output,
                    # Polling consumes successful credentials and completed error sessions.
                    side_effect=True,
                )
            )
    result.extend(
        (
            Operation(
                'platform.setup.slack.start', Permission.RESOURCE_MANAGE, slack_start, SlackStart, SessionStarted, True
            ),
            Operation('platform.setup.slack.status', Permission.RESOURCE_MANAGE, slack_status, Session, SessionStatus),
            Operation('platform.setup.slack.cancel', Permission.RESOURCE_MANAGE, slack_cancel, Session, dict, True),
        )
    )
    return result
