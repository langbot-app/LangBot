"""Short-lived Slack app provisioning and OAuth handoff sessions."""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

import aiohttp

from langbot.pkg.utils import httpclient


class SlackSetupError(ValueError):
    pass


def callback_url(webhook_url: str, bot_uuid: str) -> str:
    parsed = urlsplit(webhook_url)
    suffix = f'/bots/{bot_uuid}'
    if (
        parsed.scheme != 'https'
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith(suffix)
        or parsed.hostname.lower() == 'localhost'
    ):
        raise SlackSetupError('invalid_webhook_url')
    try:
        if not ipaddress.ip_address(parsed.hostname).is_global:
            raise SlackSetupError('invalid_webhook_url')
    except ValueError as exc:
        if isinstance(exc, SlackSetupError):
            raise
    return webhook_url[: -len(suffix)] + '/api/v1/platform/adapters/slack/setup/callback'


def manifest(name: str, webhook_url: str, redirect_url: str, *, events: bool, socket_mode=False) -> dict:
    settings = {'socket_mode_enabled': socket_mode}
    if events:
        settings['event_subscriptions'] = {
            **({} if socket_mode else {'request_url': webhook_url}),
            'bot_events': [
                'app_mention',
                'message.im',
                'message.channels',
                'message.groups',
                'message.mpim',
                'reaction_added',
                'reaction_removed',
                'member_joined_channel',
                'member_left_channel',
                'channel_rename',
                'group_rename',
                'channel_archive',
                'channel_unarchive',
                'group_archive',
                'group_unarchive',
                'app_home_opened',
                'app_uninstalled',
                'tokens_revoked',
            ],
        }
        settings['interactivity'] = {
            'is_enabled': True,
            **({} if socket_mode else {'request_url': webhook_url}),
        }
    return {
        'display_information': {'name': name},
        'features': {
            'bot_user': {'display_name': name, 'always_online': False},
            'app_home': {'messages_tab_enabled': True, 'messages_tab_read_only_enabled': False},
        },
        'oauth_config': {
            'redirect_urls': [redirect_url],
            'scopes': {
                'bot': [
                    'app_mentions:read',
                    'reactions:read',
                    'chat:write',
                    'channels:history',
                    'channels:read',
                    'groups:history',
                    'groups:read',
                    'im:history',
                    'im:read',
                    'im:write',
                    'mpim:history',
                    'mpim:read',
                    'users:read',
                    'files:read',
                    'files:write',
                ]
            },
        },
        'settings': settings,
    }


class SlackSetupService:
    TTL = 900

    def __init__(self, ap):
        self.ap = ap
        self.sessions = {}

    @staticmethod
    def scope(context):
        return (context.instance_uuid, context.workspace_uuid, context.placement_generation, context.principal)

    def owned(self, context, session_id):
        session = self.sessions.get(session_id)
        if not session or session['scope'] != self.scope(context):
            raise SlackSetupError('session_not_found')
        return session

    def discard(self, session_id):
        session = self.sessions.pop(session_id, None)
        if session:
            session['timer'].cancel()
            task = session.get('task')
            if task and not task.done():
                task.cancel()
            session.clear()

    async def api(self, method, token=None, **params):
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        try:
            async with httpclient.get_session().post(
                f'https://slack.com/api/{method}',
                data=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=25),
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise SlackSetupError(f'slack_http_{response.status}')
                data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise SlackSetupError('slack_connection_failed') from exc
        if not data.get('ok'):
            # Never surface arbitrary upstream text or credentials in errors.
            code = str(data.get('error', 'unknown_error'))
            if not re.fullmatch(r'[a-z_]{1,80}', code):
                code = 'unknown_error'
            raise SlackSetupError(code)
        return data

    async def start(
        self,
        context,
        *,
        bot_uuid,
        access_token,
        refresh_token,
        webhook_url='',
        name='LangBot',
        socket_mode=False,
        redirect_url='',
    ):
        if not all(isinstance(value, str) for value in (bot_uuid, access_token, refresh_token, webhook_url, name)):
            raise SlackSetupError('invalid_input')
        access_token, refresh_token, webhook_url, name = (
            access_token.strip(),
            refresh_token.strip(),
            webhook_url.strip(),
            name.strip(),
        )
        if not access_token or not refresh_token or not 1 <= len(name) <= 35:
            raise SlackSetupError('invalid_input')
        if not isinstance(socket_mode, bool):
            raise SlackSetupError('invalid_input')
        if socket_mode:
            parsed = urlsplit(redirect_url)
            if (
                not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or not parsed.path.endswith('/api/v1/platform/adapters/slack/setup/callback')
                or not (parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname == 'localhost'))
            ):
                raise SlackSetupError('invalid_redirect_url')
            redirect = redirect_url
        else:
            redirect = callback_url(webhook_url, bot_uuid)
        bot = await self.ap.bot_service.get_bot(context, bot_uuid)
        if not bot or bot['adapter'] not in ('slack', 'slack-omni'):
            raise SlackSetupError('slack_bot_not_found')
        if (
            len(self.sessions) >= 100
            or sum(s['context'].workspace_uuid == context.workspace_uuid for s in self.sessions.values()) >= 10
        ):
            raise SlackSetupError('too_many_sessions')
        if any(s['bot_uuid'] == bot_uuid for s in self.sessions.values()):
            raise SlackSetupError('setup_already_active')
        sid = secrets.token_urlsafe(32)
        session = {
            'scope': self.scope(context),
            'context': context,
            'status': 'creating',
            'bot_uuid': bot_uuid,
            'redirect_url': redirect,
            'webhook_url': webhook_url,
            'socket_mode': socket_mode,
            'timer': asyncio.get_running_loop().call_later(self.TTL, self.discard, sid),
        }
        self.sessions[sid] = session
        coro = self._create(session, access_token, refresh_token, name, sid)
        try:
            wrapper = self.ap.task_mgr.create_user_task(
                coro,
                kind='platform-adapter-credential-exchange',
                name=f'slack-setup-{sid}',
                label='Slack app setup',
                instance_uuid=context.instance_uuid,
                workspace_uuid=context.workspace_uuid,
                placement_generation=context.placement_generation,
            )
            session['task'] = wrapper.task
        except Exception:
            coro.close()
            self.discard(sid)
            raise SlackSetupError('too_many_sessions') from None
        return {'session_id': sid}

    async def _create(self, session, access, refresh, name, sid):
        async def config_api(method, **params):
            nonlocal access, refresh
            try:
                return await self.api(method, access, **params)
            except SlackSetupError as exc:
                if str(exc) not in ('token_expired', 'invalid_auth', 'token_revoked'):
                    raise
                rotated = await self.api('tooling.tokens.rotate', refresh_token=refresh)
                access, refresh = rotated['token'], rotated['refresh_token']
                return await self.api(method, access, **params)

        try:
            base = manifest(
                name, session['webhook_url'], session['redirect_url'], events=False, socket_mode=session['socket_mode']
            )
            result = await config_api('apps.manifest.create', manifest=json.dumps(base))
            session['app_id'] = result['app_id']
            session['credentials'] = result['credentials']
            # Register the signing secret before Slack validates the final event URL.
            complete = manifest(
                name, session['webhook_url'], session['redirect_url'], events=True, socket_mode=session['socket_mode']
            )
            await config_api('apps.manifest.update', app_id=result['app_id'], manifest=json.dumps(complete))
            session['authorize_url'] = 'https://slack.com/oauth/v2/authorize?' + urlencode(
                {
                    'client_id': result['credentials']['client_id'],
                    'scope': ','.join(complete['oauth_config']['scopes']['bot']),
                    'redirect_uri': session['redirect_url'],
                    'state': sid,
                }
            )
            session['status'] = 'waiting'
        except Exception as exc:
            if session:
                session['status'] = 'error'
                session['error'] = str(exc) if isinstance(exc, SlackSetupError) else 'setup_failed'
                session.pop('credentials', None)
        finally:
            access = refresh = ''

    def status(self, context, sid):
        session = self.owned(context, sid)
        result = {key: session[key] for key in ('status', 'app_id', 'authorize_url', 'error') if key in session}
        if session['status'] == 'success':
            result['config'] = session['config']
        return result

    async def finish(self, sid, code, error=None):
        session = self.sessions.get(sid)
        if not session or session['status'] != 'waiting':
            raise SlackSetupError('session_not_found')
        session['status'] = 'authorizing'
        try:
            if error or not code:
                raise SlackSetupError('authorization_denied')
            context = session['context']
            await self.ap.workspace_service.get_execution_binding(
                context.workspace_uuid,
                expected_generation=context.placement_generation,
            )
            creds = session['credentials']
            result = await self.api(
                'oauth.v2.access',
                client_id=creds['client_id'],
                client_secret=creds['client_secret'],
                code=code,
                redirect_uri=session['redirect_url'],
            )
            if result.get('app_id') != session['app_id'] or result.get('token_type') != 'bot':
                raise SlackSetupError('unexpected_oauth_response')
            session['config'] = {
                'bot_token': result['access_token'],
                'signing_secret': creds['signing_secret'],
                'socket_mode': session['socket_mode'],
            }
            session['status'] = 'success'
        except Exception as exc:
            if session:
                session['status'] = 'error'
                session['error'] = str(exc) if isinstance(exc, SlackSetupError) else 'authorization_failed'
            raise SlackSetupError('authorization_failed') from None
        finally:
            session.pop('credentials', None)
            session.pop('authorize_url', None)

    async def challenge(self, bot_uuid, request):
        session = next((s for s in self.sessions.values() if s['bot_uuid'] == bot_uuid and s.get('credentials')), None)
        if not session:
            return None
        body = await request.get_data()
        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > 300:
            return None
        signature = (
            'v0='
            + hmac.new(
                session['credentials']['signing_secret'].encode(),
                b'v0:' + timestamp.encode() + b':' + body,
                hashlib.sha256,
            ).hexdigest()
        )
        if not hmac.compare_digest(signature, request.headers.get('X-Slack-Signature', '')):
            return None
        data = await request.get_json(silent=True)
        if not isinstance(data, dict) or data.get('type') != 'url_verification':
            return None
        context = session['context']
        await self.ap.workspace_service.get_execution_binding(
            context.workspace_uuid,
            expected_generation=context.placement_generation,
        )
        return {'challenge': data.get('challenge', '')}


def get_slack_setup(ap):
    if not hasattr(ap, 'slack_setup_service'):
        ap.slack_setup_service = SlackSetupService(ap)
    return ap.slack_setup_service
