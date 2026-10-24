from langbot.pkg.i18n import t, DEFAULT_LANGUAGE
from langbot.pkg.i18n.workspace import get_workspace_language
import mimetypes

import quart

from langbot.pkg.api.http.authz import Permission
from langbot.pkg.api.http.context import RequestContext
from langbot.pkg.cloud.plan_policy import workspace_entitlement, platform_feature_names, require_workspace_platform
from langbot.pkg.utils import importutil

from ... import group

from langbot.pkg.platform.credential_setup import (
    _AdapterSessionScope as _AdapterSessionScope,
    _bind_session_scope as _bind_session_scope,
    _get_owned_session as _get_owned_session,
    _pop_owned_session as _pop_owned_session,
    _scrub_credential_fields as _scrub_credential_fields,
    _sweep_credential_sessions as _sweep_credential_sessions,
    _start_adapter_session_task as _start_adapter_session_task,
    _make_room_for_session as _make_room_for_session,
    _decrypt_qqofficial_secret as _decrypt_qqofficial_secret,
    CredentialSetupError,
    get_credential_setup,
)


@group.group_class('adapters', '/api/v1/platform/adapters')
class AdaptersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        from ....service.slack_setup import get_slack_setup, SlackSetupError

        slack_setup = get_slack_setup(self.ap)

        @self.route(
            '/slack/setup',
            methods=['POST'],
            permission=Permission.RESOURCE_MANAGE,
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def slack_start(request_context: RequestContext):
            data = await quart.request.get_json()
            if not isinstance(data, dict):
                return self.http_status(400, -1, 'invalid_input')
            try:
                result = await slack_setup.start(
                    request_context,
                    **{
                        key: data[key]
                        for key in (
                            'bot_uuid',
                            'access_token',
                            'refresh_token',
                            'webhook_url',
                            'name',
                            'socket_mode',
                            'redirect_url',
                        )
                        if key in data
                    },
                )
                return self.success(data=result)
            except (SlackSetupError, TypeError) as exc:
                return self.http_status(400, -1, str(exc) if isinstance(exc, SlackSetupError) else 'invalid_input')

        @self.route(
            '/slack/setup/<session_id>',
            methods=['GET', 'DELETE'],
            permission=Permission.RESOURCE_MANAGE,
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def slack_status(session_id: str, request_context: RequestContext):
            try:
                slack_setup.owned(request_context, session_id)
                if quart.request.method == 'DELETE':
                    slack_setup.discard(session_id)
                    return self.success(data={})
                response = await quart.make_response(self.success(data=slack_setup.status(request_context, session_id)))
                response.headers['Cache-Control'] = 'no-store'
                return response
            except SlackSetupError:
                return self.http_status(404, -1, 'session_not_found')

        @self.route('/slack/setup/callback', methods=['GET'], auth_type=group.AuthType.NONE)
        async def slack_callback():
            session = slack_setup.sessions.get(quart.request.args.get('state', ''))
            locale = DEFAULT_LANGUAGE
            if session is not None:
                locale = await get_workspace_language(self.ap, session['context'].workspace_uuid)
            try:
                await slack_setup.finish(
                    quart.request.args.get('state', ''),
                    quart.request.args.get('code', ''),
                    quart.request.args.get('error'),
                )
                message = t('Slack authorization completed. Return to LangBot to finish setup.', locale=locale)
                status = 200
            except SlackSetupError:
                message = t('Slack authorization failed or expired. Return to LangBot for details.', locale=locale)
                status = 400
            return quart.Response(
                message,
                status=status,
                content_type='text/plain; charset=utf-8',
                headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'},
            )

        @self.route('', methods=['GET'])
        async def _(request_context: RequestContext) -> str:
            snapshot = await workspace_entitlement(self.ap, request_context.workspace_uuid)
            adapters = self.ap.platform_mgr.get_available_adapters_info()
            if snapshot is not None:
                adapters = [
                    a
                    for a in adapters
                    if not any(snapshot.features.get(f) is False for f in platform_feature_names(a['name']))
                ]
            return self.success(data={'adapters': adapters})

        @self.route('/<adapter_name>', methods=['GET'])
        async def _(adapter_name: str, request_context: RequestContext) -> str:
            await require_workspace_platform(self.ap, request_context.workspace_uuid, adapter_name)
            adapter_info = self.ap.platform_mgr.get_available_adapter_info_by_name(adapter_name)

            if adapter_info is None:
                return self.http_status(404, -1, 'adapter not found')

            return self.success(data={'adapter': adapter_info})

        @self.route('/<adapter_name>/icon', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _(adapter_name: str) -> quart.Response:
            adapter_manifest = self.ap.platform_mgr.get_available_adapter_manifest_by_name(adapter_name)

            if adapter_manifest is None:
                return self.http_status(404, -1, 'adapter not found')

            icon_path = adapter_manifest.icon_rel_path

            if icon_path is None:
                return self.http_status(404, -1, 'icon not found')

            return quart.Response(
                importutil.read_resource_file_bytes(icon_path), mimetype=mimetypes.guess_type(icon_path)[0]
            )

        @self.route('/dingtalk/stream-card-template', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> quart.Response:
            filename = 'dingtalk_stream_card.json'
            response = quart.Response(
                importutil.read_resource_file_bytes(f'templates/{filename}'), mimetype='application/json'
            )
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return response

        @self.route('/dingtalk/human-input-card-template', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> quart.Response:
            filename = 'dingtalk_human_input_card.json'
            response = quart.Response(
                importutil.read_resource_file_bytes(f'templates/{filename}'), mimetype='application/json'
            )
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return response

        # In-memory session store for active registrations
        credential_setup = get_credential_setup(self.ap)
        self._sweep_credential_sessions = credential_setup._sweep_credential_sessions

        @self.route('/lark/create-app', methods=['POST'], permission=Permission.RESOURCE_MANAGE)
        async def lark_start(request_context: RequestContext) -> str:
            try:
                result = await credential_setup.lark_start(request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/lark/create-app/status/<session_id>',
            methods=['GET'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def lark_status(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.lark_status(session_id=session_id, request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/lark/create-app/<session_id>',
            methods=['DELETE'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def lark_cancel(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.lark_cancel(session_id=session_id, request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route('/weixin/login', methods=['POST'], permission=Permission.RESOURCE_MANAGE)
        async def weixin_start(request_context: RequestContext) -> str:
            try:
                result = await credential_setup.weixin_start(request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/weixin/login/status/<session_id>',
            methods=['GET'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def weixin_status(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.weixin_status(session_id=session_id, request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/weixin/login/<session_id>',
            methods=['DELETE'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def weixin_cancel(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.weixin_cancel(session_id=session_id, request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route('/dingtalk/create-app', methods=['POST'], permission=Permission.RESOURCE_MANAGE)
        async def dingtalk_start(request_context: RequestContext) -> str:
            try:
                result = await credential_setup.dingtalk_start(request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/dingtalk/create-app/status/<session_id>',
            methods=['GET'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def dingtalk_status(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.dingtalk_status(session_id=session_id, request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/dingtalk/create-app/<session_id>',
            methods=['DELETE'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def dingtalk_cancel(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.dingtalk_cancel(session_id=session_id, request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route('/wecombot/create-bot', methods=['POST'], permission=Permission.RESOURCE_MANAGE)
        async def wecombot_start(request_context: RequestContext) -> str:
            try:
                result = await credential_setup.wecombot_start(request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/wecombot/create-bot/status/<session_id>',
            methods=['GET'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def wecombot_status(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.wecombot_status(session_id=session_id, request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/wecombot/create-bot/<session_id>',
            methods=['DELETE'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def wecombot_cancel(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.wecombot_cancel(session_id=session_id, request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route('/qqofficial/bind', methods=['POST'], permission=Permission.RESOURCE_MANAGE)
        async def qqofficial_start(request_context: RequestContext) -> str:
            try:
                result = await credential_setup.qqofficial_start(request_context=request_context)
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/qqofficial/bind/status/<session_id>',
            methods=['GET'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def qqofficial_status(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.qqofficial_status(
                    session_id=session_id, request_context=request_context
                )
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))

        @self.route(
            '/qqofficial/bind/<session_id>',
            methods=['DELETE'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def qqofficial_cancel(session_id: str, request_context: RequestContext) -> str:
            try:
                result = await credential_setup.qqofficial_cancel(
                    session_id=session_id, request_context=request_context
                )
                return self.success(data=result)
            except CredentialSetupError as exc:
                return self.http_status(exc.status_code, -1, str(exc))
