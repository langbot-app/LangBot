"""Principal-scoped platform credential exchanges shared by application entrypoints."""

from __future__ import annotations

import asyncio
import dataclasses
import logging

from langbot.pkg.api.context import RequestContext
from langbot.pkg.core.errors import TaskCapacityError
from langbot.pkg.utils import httpclient


@dataclasses.dataclass(frozen=True, slots=True)
class _AdapterSessionScope:
    """Immutable tenant and principal binding for a credential exchange."""

    instance_uuid: str
    workspace_uuid: str
    placement_generation: int
    principal_type: str
    account_uuid: str | None
    api_key_uuid: str | None
    support_session_id: str | None

    @classmethod
    def from_request_context(cls, request_context: RequestContext) -> '_AdapterSessionScope':
        principal = request_context.principal
        return cls(
            instance_uuid=request_context.instance_uuid,
            workspace_uuid=request_context.workspace_uuid,
            placement_generation=request_context.placement_generation,
            principal_type=principal.principal_type.value,
            account_uuid=principal.account_uuid,
            api_key_uuid=principal.api_key_uuid,
            support_session_id=principal.support_session_id,
        )

    def matches(self, request_context: RequestContext) -> bool:
        """Return whether a request is from the exact initiating tenant principal."""

        return self == self.from_request_context(request_context)


def _bind_session_scope(session: dict, request_context: RequestContext) -> None:
    session['scope'] = _AdapterSessionScope.from_request_context(request_context)


def _get_owned_session(
    sessions: dict[str, dict],
    session_id: str,
    request_context: RequestContext,
) -> dict | None:
    """Resolve a session without revealing sessions owned by another scope."""

    session = sessions.get(session_id)
    scope = session.get('scope') if session is not None else None
    if not isinstance(scope, _AdapterSessionScope) or not scope.matches(request_context):
        return None
    return session


def _pop_owned_session(
    sessions: dict[str, dict],
    session_id: str,
    request_context: RequestContext,
) -> dict | None:
    """Remove an owned session without allowing cross-scope cancellation."""

    session = _get_owned_session(sessions, session_id, request_context)
    if session is None:
        return None
    return sessions.pop(session_id, None)


_MAX_ADAPTER_SESSIONS = 100
# How often the credential-session sweeper enforces its TTL, independent of traffic.
_CREDENTIAL_SWEEP_INTERVAL_SECONDS = 60
_MAX_ADAPTER_SESSIONS_PER_WORKSPACE = 10


def _scrub_credential_fields(session: dict) -> None:
    """Overwrite credential fields before a session dict is dropped."""
    for key in ('app_secret', 'client_secret', 'secret'):
        if key in session:
            session[key] = None


def _sweep_credential_sessions(stores: 'list[tuple[dict, float]]') -> int:
    """Evict sessions past their TTL and scrub the secrets they held.

    Returns the number of evicted sessions. Each entry is ``(store, ttl)``; a
    session is evicted when ``now - created_at > ttl``.
    """
    import time

    now = time.time()
    evicted = 0
    for store, ttl in stores:
        expired = [sid for sid, session in store.items() if now - session.get('created_at', 0) > ttl]
        for sid in expired:
            session = store.pop(sid, None)
            if not session:
                continue
            task = session.get('task')
            if task is not None and not task.done():
                task.cancel()
            _scrub_credential_fields(session)
            evicted += 1
    return evicted


def _start_adapter_session_task(
    ap,
    coro,
    *,
    adapter: str,
    session_id: str,
    request_context: RequestContext,
) -> asyncio.Task | None:
    """Attach one credential exchange to tenant admission and app shutdown."""

    try:
        wrapper = ap.task_mgr.create_user_task(
            coro,
            kind='platform-adapter-credential-exchange',
            name=f'{adapter}-credential-{session_id}',
            label=f'{adapter} credential exchange',
            instance_uuid=request_context.instance_uuid,
            workspace_uuid=request_context.workspace_uuid,
            placement_generation=request_context.placement_generation,
        )
    except TaskCapacityError:
        coro.close()
        return None
    return wrapper.task


def _make_room_for_session(
    sessions: dict[str, dict],
    request_context: RequestContext,
) -> None:
    """Bound credential-exchange sessions globally and per workspace."""

    workspace_uuid = request_context.workspace_uuid
    owned = [
        (session_id, session)
        for session_id, session in sessions.items()
        if getattr(session.get('scope'), 'workspace_uuid', None) == workspace_uuid
    ]
    evict_workspace_session = len(owned) >= _MAX_ADAPTER_SESSIONS_PER_WORKSPACE
    evict_global_session = len(sessions) >= _MAX_ADAPTER_SESSIONS
    if not evict_workspace_session and not evict_global_session:
        return

    candidates = owned if evict_workspace_session else list(sessions.items())
    session_id, _ = min(
        candidates,
        key=lambda item: float(item[1].get('created_at', 0.0)),
    )
    session = sessions.pop(session_id, None)
    task = session.get('task') if session is not None else None
    if task is not None and not task.done():
        task.cancel()


def _decrypt_qqofficial_secret(encrypted_b64: str, key: bytes) -> str:
    """Decrypt the AppSecret returned by the QQ Official QR binding endpoint.

    The base64 payload is laid out as `nonce (12 B) | ciphertext | tag (16 B)`.
    `key` is the 32-byte AES-256 key locally generated when the bind task
    was created and submitted as `key` to `q.qq.com/lite/create_bind_task`.
    """
    import base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        raw = base64.b64decode(encrypted_b64)
    except Exception as exc:
        raise ValueError('Malformed encrypted credential') from exc
    if len(key) != 32 or len(raw) <= 28:
        raise ValueError('Invalid encrypted credential layout')
    nonce, ciphertext, tag = raw[:12], raw[12:-16], raw[-16:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext + tag, None).decode('utf-8')
    except Exception as exc:
        raise ValueError('Failed to decrypt credential') from exc


class CredentialSetupError(RuntimeError):
    error_code = 'credential_setup_failed'

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


class CredentialSetupService:
    def __init__(self, ap):
        self.ap = ap
        _create_app_sessions: dict = {}
        _SESSION_TTL = 900  # 15 minutes

        def _cleanup_expired_sessions():
            """Remove sessions that have exceeded their TTL."""
            import time

            now = time.time()
            expired = [sid for sid, s in _create_app_sessions.items() if now - s.get('created_at', 0) > _SESSION_TTL]
            for sid in expired:
                session = _create_app_sessions.pop(sid, None)
                if session and session.get('task') and not session['task'].done():
                    session['task'].cancel()

        async def lark_start(request_context: RequestContext) -> dict:
            """Start Feishu one-click app registration. Returns session_id + QR code URL."""
            import uuid
            import time
            import lark_oapi as lark
            from lark_oapi.scene.registration.errors import AppAccessDeniedError, AppExpiredError

            _cleanup_expired_sessions()

            session_id = str(uuid.uuid4())
            loop = asyncio.get_running_loop()

            session = {
                'status': 'pending',
                'qr_url': None,
                'expire_at': None,
                'app_id': None,
                'app_secret': None,
                'error': None,
                'created_at': time.time(),
            }
            _bind_session_scope(session, request_context)
            _make_room_for_session(_create_app_sessions, request_context)
            _create_app_sessions[session_id] = session

            def on_qr_code(info):
                # May be called from a background thread by the SDK;
                # use call_soon_threadsafe to safely update session state.
                def _update():
                    session['qr_url'] = info['url']
                    session['expire_at'] = time.time() + 600  # 10 minutes
                    session['status'] = 'waiting'

                loop.call_soon_threadsafe(_update)

            async def run_registration():
                try:
                    result = await lark.aregister_app(
                        on_qr_code=on_qr_code,
                        source='langbot',
                    )
                    session['status'] = 'success'
                    session['app_id'] = result['client_id']
                    session['app_secret'] = result['client_secret']
                except AppAccessDeniedError:
                    session['status'] = 'error'
                    session['error'] = 'User denied authorization'
                except AppExpiredError:
                    session['status'] = 'error'
                    session['error'] = 'QR code expired'
                except Exception as e:
                    session['status'] = 'error'
                    session['error'] = str(e)

            task = _start_adapter_session_task(
                self.ap,
                run_registration(),
                adapter='lark',
                session_id=session_id,
                request_context=request_context,
            )
            if task is None:
                _create_app_sessions.pop(session_id, None)
                raise CredentialSetupError(429, 'Too many active credential exchanges')
            session['task'] = task

            # Wait for QR code to be ready (max 10 seconds)
            for _ in range(20):
                if session['qr_url']:
                    break
                await asyncio.sleep(0.5)

            if not session['qr_url']:
                task.cancel()
                session['status'] = 'error'
                session['error'] = 'Timeout waiting for QR code'
                raise CredentialSetupError(504, 'Timeout waiting for QR code')

            return {
                'session_id': session_id,
                'qr_url': session['qr_url'],
                'expire_at': session['expire_at'],
            }

        async def lark_status(session_id: str, request_context: RequestContext) -> dict:
            """Poll registration status."""
            _cleanup_expired_sessions()
            session = _get_owned_session(_create_app_sessions, session_id, request_context)
            if not session:
                raise CredentialSetupError(404, 'Session not found')

            data = {'status': session['status']}

            if session['status'] == 'success':
                data['app_id'] = session['app_id']
                data['app_secret'] = session['app_secret']
                _create_app_sessions.pop(session_id, None)
            elif session['status'] == 'error':
                data['error'] = session['error']
                _create_app_sessions.pop(session_id, None)

            return data

        async def lark_cancel(session_id: str, request_context: RequestContext) -> dict:
            """Cancel and clean up a registration session."""
            session = _pop_owned_session(_create_app_sessions, session_id, request_context)
            if session is None:
                raise CredentialSetupError(404, 'Session not found')
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return {}

        # -----------------------------------------------------------------------
        # WeChat QR Code Login
        # -----------------------------------------------------------------------

        _weixin_login_sessions: dict = {}
        _WEIXIN_SESSION_TTL = 600  # 10 minutes (3 retries × 3 min QR validity)

        def _cleanup_expired_weixin_sessions():
            import time

            now = time.time()
            expired = [
                sid for sid, s in _weixin_login_sessions.items() if now - s.get('created_at', 0) > _WEIXIN_SESSION_TTL
            ]
            for sid in expired:
                session = _weixin_login_sessions.pop(sid, None)
                if session and session.get('task') and not session['task'].done():
                    session['task'].cancel()

        async def weixin_start(request_context: RequestContext) -> dict:
            """Start WeChat QR code login. Returns session_id + QR code data URL."""
            import uuid
            import time

            from langbot.libs.openclaw_weixin_api.client import OpenClawWeixinClient, DEFAULT_BASE_URL

            _cleanup_expired_weixin_sessions()

            session_id = str(uuid.uuid4())
            loop = asyncio.get_running_loop()

            session = {
                'status': 'pending',
                'qr_data_url': None,
                'expire_at': None,
                'token': None,
                'base_url': None,
                'account_id': None,
                'error': None,
                'created_at': time.time(),
            }
            _bind_session_scope(session, request_context)
            _make_room_for_session(_weixin_login_sessions, request_context)
            _weixin_login_sessions[session_id] = session

            client = OpenClawWeixinClient(
                base_url=DEFAULT_BASE_URL,
                token='',
            )

            async def run_login():
                try:

                    def on_qrcode(qr_data_url: str, _qr_url: str):
                        def _update():
                            session['qr_data_url'] = qr_data_url
                            session['expire_at'] = time.time() + 180
                            session['status'] = 'waiting'

                        loop.call_soon_threadsafe(_update)

                    result = await client.login(
                        max_retries=1,
                        poll_timeout_ms=180_000,
                        on_qrcode=on_qrcode,
                    )
                    session['status'] = 'success'
                    session['token'] = result.token
                    session['base_url'] = result.base_url
                    session['account_id'] = result.account_id
                except Exception as e:
                    error_message = str(e)
                    if 'expired' in error_message.lower() or 'max retries exceeded' in error_message.lower():
                        session['status'] = 'expired'
                        session['error'] = 'QR code expired'
                    else:
                        session['status'] = 'error'
                        session['error'] = error_message
                finally:
                    await client.close()

            task = _start_adapter_session_task(
                self.ap,
                run_login(),
                adapter='weixin',
                session_id=session_id,
                request_context=request_context,
            )
            if task is None:
                _weixin_login_sessions.pop(session_id, None)
                raise CredentialSetupError(429, 'Too many active credential exchanges')
            session['task'] = task

            # Wait for QR code to be ready (max 10 seconds)
            for _ in range(20):
                if session['qr_data_url']:
                    break
                await asyncio.sleep(0.5)

            if not session['qr_data_url']:
                task.cancel()
                session['status'] = 'error'
                session['error'] = 'Timeout waiting for QR code'
                raise CredentialSetupError(504, 'Timeout waiting for QR code')

            return {
                'session_id': session_id,
                'qr_data_url': session['qr_data_url'],
                'expire_at': session['expire_at'],
            }

        async def weixin_status(session_id: str, request_context: RequestContext) -> dict:
            """Poll WeChat login status."""
            _cleanup_expired_weixin_sessions()
            session = _get_owned_session(_weixin_login_sessions, session_id, request_context)
            if not session:
                raise CredentialSetupError(404, 'Session not found')

            data = {
                'status': session['status'],
                'qr_data_url': session['qr_data_url'],
                'expire_at': session['expire_at'],
            }

            if session['status'] == 'success':
                data['token'] = session['token']
                data['base_url'] = session['base_url']
                data['account_id'] = session['account_id']
                _weixin_login_sessions.pop(session_id, None)
            elif session['status'] == 'error':
                data['error'] = session['error']
                _weixin_login_sessions.pop(session_id, None)
            elif session['status'] == 'expired':
                data['error'] = session['error']
                _weixin_login_sessions.pop(session_id, None)

            return data

        async def weixin_cancel(session_id: str, request_context: RequestContext) -> dict:
            """Cancel and clean up a WeChat login session."""
            session = _pop_owned_session(_weixin_login_sessions, session_id, request_context)
            if session is None:
                raise CredentialSetupError(404, 'Session not found')
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return {}

        # -----------------------------------------------------------------------
        # DingTalk Device Flow QR Code Login
        # -----------------------------------------------------------------------

        _dingtalk_sessions: dict = {}
        _DINGTALK_SESSION_TTL = 600  # 10 minutes (QR code validity window)

        def _cleanup_expired_dingtalk_sessions():
            import time

            now = time.time()
            expired = [
                sid for sid, s in _dingtalk_sessions.items() if now - s.get('created_at', 0) > _DINGTALK_SESSION_TTL
            ]
            for sid in expired:
                session = _dingtalk_sessions.pop(sid, None)
                if session and session.get('task') and not session['task'].done():
                    session['task'].cancel()

        async def dingtalk_start(request_context: RequestContext) -> dict:
            """Start DingTalk one-click app creation via Device Flow. Returns session_id + QR code URL."""
            import uuid
            import time
            import aiohttp

            DINGTALK_BASE_URL = 'https://oapi.dingtalk.com'

            _cleanup_expired_dingtalk_sessions()

            session_id = str(uuid.uuid4())

            session = {
                'status': 'pending',
                'qr_url': None,
                'expire_at': None,
                'client_id': None,
                'client_secret': None,
                'error': None,
                'created_at': time.time(),
                'device_code': None,
                'interval': 5,
            }
            _bind_session_scope(session, request_context)
            _make_room_for_session(_dingtalk_sessions, request_context)
            _dingtalk_sessions[session_id] = session

            async def run_device_flow():
                try:
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with aiohttp.ClientSession(timeout=timeout) as http:
                        # Step 1: Init — get nonce
                        async with http.post(
                            f'{DINGTALK_BASE_URL}/app/registration/init',
                            json={'source': 'langbot'},
                        ) as resp:
                            try:
                                data = await httpclient.read_json_limited(resp)
                            except (aiohttp.ContentTypeError, ValueError):
                                session['status'] = 'error'
                                session['error'] = 'Invalid response from DingTalk service'
                                return
                            if data.get('errcode', -1) != 0:
                                session['status'] = 'error'
                                session['error'] = data.get('errmsg', 'Failed to init')
                                return
                            nonce = data['nonce']

                        # Step 2: Begin — get device_code + QR URL
                        async with http.post(
                            f'{DINGTALK_BASE_URL}/app/registration/begin',
                            json={'nonce': nonce},
                        ) as resp:
                            try:
                                data = await httpclient.read_json_limited(resp)
                            except (aiohttp.ContentTypeError, ValueError):
                                session['status'] = 'error'
                                session['error'] = 'Invalid response from DingTalk service'
                                return
                            if data.get('errcode', -1) != 0:
                                session['status'] = 'error'
                                session['error'] = data.get('errmsg', 'Failed to begin authorization')
                                return

                            device_code = data['device_code']
                            verification_uri_complete = data.get('verification_uri_complete', '')
                            expires_in = data.get('expires_in', 7200)
                            interval = data.get('interval', 5)

                            session['device_code'] = device_code
                            session['interval'] = interval
                            session['qr_url'] = verification_uri_complete
                            session['expire_at'] = time.time() + 600  # QR code valid for ~10 min
                            session['status'] = 'waiting'

                        # Step 3: Poll for authorization result
                        deadline = time.time() + expires_in
                        while time.time() < deadline:
                            await asyncio.sleep(interval)

                            async with http.post(
                                f'{DINGTALK_BASE_URL}/app/registration/poll',
                                json={'device_code': device_code},
                            ) as poll_resp:
                                try:
                                    poll_data = await httpclient.read_json_limited(poll_resp)
                                except (aiohttp.ContentTypeError, ValueError):
                                    continue

                                if poll_data.get('errcode', -1) != 0:
                                    session['status'] = 'error'
                                    session['error'] = poll_data.get('errmsg', 'Poll failed')
                                    return

                                status = poll_data.get('status', '')

                                if status == 'SUCCESS':
                                    session['status'] = 'success'
                                    session['client_id'] = poll_data.get('client_id', '')
                                    session['client_secret'] = poll_data.get('client_secret', '')
                                    return
                                elif status == 'FAIL':
                                    session['status'] = 'error'
                                    session['error'] = poll_data.get('fail_reason', 'Authorization failed')
                                    return
                                elif status == 'EXPIRED':
                                    session['status'] = 'error'
                                    session['error'] = 'QR code expired'
                                    return
                                # status == 'WAITING': continue polling

                        # Timeout
                        session['status'] = 'error'
                        session['error'] = 'QR code expired'

                except asyncio.CancelledError:
                    return
                except Exception as e:
                    session['status'] = 'error'
                    session['error'] = str(e)

            task = _start_adapter_session_task(
                self.ap,
                run_device_flow(),
                adapter='dingtalk',
                session_id=session_id,
                request_context=request_context,
            )
            if task is None:
                _dingtalk_sessions.pop(session_id, None)
                raise CredentialSetupError(429, 'Too many active credential exchanges')
            session['task'] = task

            # Wait for QR code to be ready (max 10 seconds)
            for _ in range(20):
                if session['qr_url'] or session['error']:
                    break
                await asyncio.sleep(0.5)

            if session['error']:
                task.cancel()
                raise CredentialSetupError(502, session['error'])

            if not session['qr_url']:
                task.cancel()
                session['status'] = 'error'
                session['error'] = 'Timeout waiting for QR code'
                raise CredentialSetupError(504, 'Timeout waiting for QR code')

            return {
                'session_id': session_id,
                'qr_url': session['qr_url'],
                'expire_at': session['expire_at'],
            }

        async def dingtalk_status(session_id: str, request_context: RequestContext) -> dict:
            """Poll DingTalk Device Flow status."""
            _cleanup_expired_dingtalk_sessions()
            session = _get_owned_session(_dingtalk_sessions, session_id, request_context)
            if not session:
                raise CredentialSetupError(404, 'Session not found')

            data = {'status': session['status']}

            if session['status'] == 'success':
                data['client_id'] = session['client_id']
                data['client_secret'] = session['client_secret']
                _dingtalk_sessions.pop(session_id, None)
            elif session['status'] == 'error':
                data['error'] = session['error']
                _dingtalk_sessions.pop(session_id, None)

            return data

        async def dingtalk_cancel(session_id: str, request_context: RequestContext) -> dict:
            """Cancel and clean up a DingTalk Device Flow session."""
            session = _pop_owned_session(_dingtalk_sessions, session_id, request_context)
            if session is None:
                raise CredentialSetupError(404, 'Session not found')
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return {}

        # -----------------------------------------------------------------------
        # WeComBot QR Code One-Click Create
        # -----------------------------------------------------------------------

        _wecombot_sessions: dict = {}
        _WECOMBOT_SESSION_TTL = 300  # 5 minutes (WeCom QR validity window)

        def _cleanup_expired_wecombot_sessions():
            import time

            now = time.time()
            expired = [
                sid for sid, s in _wecombot_sessions.items() if now - s.get('created_at', 0) > _WECOMBOT_SESSION_TTL
            ]
            for sid in expired:
                session = _wecombot_sessions.pop(sid, None)
                if session and session.get('task') and not session['task'].done():
                    session['task'].cancel()

        async def wecombot_start(request_context: RequestContext) -> dict:
            """Start WeComBot one-click creation via QR code. Returns session_id + QR code URL."""
            import uuid
            import time
            import aiohttp

            WECOM_QC_GENERATE_URL = 'https://work.weixin.qq.com/ai/qc/generate'
            WECOM_QC_QUERY_URL = 'https://work.weixin.qq.com/ai/qc/query_result'

            _cleanup_expired_wecombot_sessions()

            session_id = str(uuid.uuid4())

            session = {
                'status': 'pending',
                'qr_url': None,
                'expire_at': None,
                'botid': None,
                'secret': None,
                'error': None,
                'created_at': time.time(),
                'scode': None,
                'task': None,
            }
            _bind_session_scope(session, request_context)
            _make_room_for_session(_wecombot_sessions, request_context)
            _wecombot_sessions[session_id] = session

            async def run_qr_flow():
                try:
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with aiohttp.ClientSession(timeout=timeout) as http:
                        # Step 1: Generate QR code
                        async with http.get(
                            f'{WECOM_QC_GENERATE_URL}?source=langbot&plat=0',
                        ) as resp:
                            try:
                                data = await httpclient.read_json_limited(resp)
                            except (aiohttp.ContentTypeError, ValueError):
                                session['status'] = 'error'
                                session['error'] = 'Invalid response from WeCom service'
                                return
                            if not data.get('data', {}).get('scode') or not data.get('data', {}).get('auth_url'):
                                session['status'] = 'error'
                                session['error'] = data.get('errmsg', 'Failed to generate QR code')
                                return

                            scode = data['data']['scode']
                            auth_url = data['data']['auth_url']

                            session['scode'] = scode
                            session['qr_url'] = auth_url
                            session['expire_at'] = time.time() + _WECOMBOT_SESSION_TTL
                            session['status'] = 'waiting'

                        # Step 2: Poll for scan result
                        deadline = time.time() + _WECOMBOT_SESSION_TTL
                        while time.time() < deadline:
                            await asyncio.sleep(3)

                            async with http.get(
                                f'{WECOM_QC_QUERY_URL}?scode={scode}',
                            ) as poll_resp:
                                try:
                                    poll_data = await httpclient.read_json_limited(poll_resp)
                                except (aiohttp.ContentTypeError, ValueError):
                                    continue

                                status = poll_data.get('data', {}).get('status', '')
                                if status == 'success':
                                    bot_info = poll_data.get('data', {}).get('bot_info', {})
                                    if bot_info.get('botid') and bot_info.get('secret'):
                                        session['status'] = 'success'
                                        session['botid'] = bot_info['botid']
                                        session['secret'] = bot_info['secret']
                                        return
                                    else:
                                        session['status'] = 'error'
                                        session['error'] = 'Scan succeeded but bot info is incomplete'
                                        return

                        # Timeout
                        session['status'] = 'error'
                        session['error'] = 'QR code expired'

                except asyncio.CancelledError:
                    return
                except Exception as e:
                    session['status'] = 'error'
                    session['error'] = str(e)

            task = _start_adapter_session_task(
                self.ap,
                run_qr_flow(),
                adapter='wecombot',
                session_id=session_id,
                request_context=request_context,
            )
            if task is None:
                _wecombot_sessions.pop(session_id, None)
                raise CredentialSetupError(429, 'Too many active credential exchanges')
            session['task'] = task

            # Wait for QR code to be ready (max 10 seconds)
            for _ in range(20):
                if session['qr_url'] or session['error']:
                    break
                await asyncio.sleep(0.5)

            if session['error']:
                task.cancel()
                raise CredentialSetupError(502, session['error'])

            if not session['qr_url']:
                task.cancel()
                session['status'] = 'error'
                session['error'] = 'Timeout waiting for QR code'
                raise CredentialSetupError(504, 'Timeout waiting for QR code')

            return {
                'session_id': session_id,
                'qr_url': session['qr_url'],
                'expire_at': session['expire_at'],
            }

        async def wecombot_status(session_id: str, request_context: RequestContext) -> dict:
            """Poll WeComBot creation status."""
            _cleanup_expired_wecombot_sessions()
            session = _get_owned_session(_wecombot_sessions, session_id, request_context)
            if not session:
                raise CredentialSetupError(404, 'Session not found')

            data = {'status': session['status']}

            if session['status'] == 'success':
                data['botid'] = session['botid']
                data['secret'] = session['secret']
                _wecombot_sessions.pop(session_id, None)
            elif session['status'] == 'error':
                data['error'] = session['error']
                _wecombot_sessions.pop(session_id, None)

            return data

        async def wecombot_cancel(session_id: str, request_context: RequestContext) -> dict:
            """Cancel and clean up a WeComBot creation session."""
            session = _pop_owned_session(_wecombot_sessions, session_id, request_context)
            if session is None:
                raise CredentialSetupError(404, 'Session not found')
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return {}

        # -----------------------------------------------------------------------
        # QQ Official QR Binding
        # -----------------------------------------------------------------------

        _qqofficial_sessions: dict = {}
        _QQOFFICIAL_SESSION_TTL = 300  # 5 minutes (QQ bind QR validity window)

        def _cleanup_expired_qqofficial_sessions():
            import time

            now = time.time()
            expired = [
                sid for sid, s in _qqofficial_sessions.items() if now - s.get('created_at', 0) > _QQOFFICIAL_SESSION_TTL
            ]
            for sid in expired:
                session = _qqofficial_sessions.pop(sid, None)
                if session and session.get('task') and not session['task'].done():
                    session['task'].cancel()

        async def qqofficial_start(request_context: RequestContext) -> dict:
            """Start QQ Official QR binding. Returns session_id + QR URL.

            Flow: generate a local AES-256 key, register it with
            `q.qq.com/lite/create_bind_task`, then poll
            `q.qq.com/lite/poll_bind_result` until the user authorizes the
            bind inside the QQ Bot Assistant on mobile QQ. The encrypted
            AppSecret returned by the poll endpoint is decrypted with the
            same key. The key never leaves this process.
            """
            import uuid
            import time
            import secrets
            import base64
            import aiohttp

            QQ_BIND_BASE = 'https://q.qq.com'
            _cleanup_expired_qqofficial_sessions()

            bind_key_bytes = secrets.token_bytes(32)
            bind_key = base64.b64encode(bind_key_bytes).decode('ascii')

            session_id = str(uuid.uuid4())
            session = {
                'status': 'pending',
                'qr_url': None,
                'expire_at': None,
                'appid': None,
                'secret': None,
                'user_openid': None,
                'error': None,
                'created_at': time.time(),
                'task_id': None,
                'bind_key_bytes': bind_key_bytes,
                'interval': 2,
            }
            _bind_session_scope(session, request_context)
            _make_room_for_session(_qqofficial_sessions, request_context)
            _qqofficial_sessions[session_id] = session

            async def run_qr_binding():
                try:
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with aiohttp.ClientSession(timeout=timeout) as http:
                        # Step 1: create_bind_task — register our AES key, get task_id
                        async with http.post(
                            f'{QQ_BIND_BASE}/lite/create_bind_task',
                            json={'key': bind_key},
                            headers={'Accept': 'application/json'},
                        ) as resp:
                            try:
                                data = await httpclient.read_json_limited(resp)
                            except (aiohttp.ContentTypeError, ValueError):
                                session['status'] = 'error'
                                session['error'] = 'Invalid response from QQ bind service'
                                return
                            if int(data.get('retcode', -1)) != 0:
                                session['status'] = 'error'
                                session['error'] = (
                                    data.get('msg') or data.get('message') or 'Failed to create bind task'
                                )
                                return
                            task_id = str((data.get('data') or {}).get('task_id') or '').strip()
                            if not task_id:
                                session['status'] = 'error'
                                session['error'] = 'Missing task_id in QQ response'
                                return

                        # The QR encodes a URL that mobile QQ opens inside the QQ Bot Assistant.
                        # `source=langbot` is a courtesy attribution parameter so Tencent
                        # can see LangBot adoption metrics, matching the convention used by
                        # other third-party integrations (e.g. hermes-agent uses `source=hermes`).
                        qr_url = f'{QQ_BIND_BASE}/qqbot/openclaw/connect.html?task_id={task_id}&_wv=2&source=langbot'
                        session['task_id'] = task_id
                        session['qr_url'] = qr_url
                        session['expire_at'] = time.time() + _QQOFFICIAL_SESSION_TTL
                        session['status'] = 'waiting'

                        # Step 2: poll_bind_result until completed (status=2) or expired (3).
                        deadline = time.time() + _QQOFFICIAL_SESSION_TTL
                        while time.time() < deadline:
                            await asyncio.sleep(session['interval'])

                            async with http.post(
                                f'{QQ_BIND_BASE}/lite/poll_bind_result',
                                json={'task_id': task_id},
                                headers={'Accept': 'application/json'},
                            ) as poll_resp:
                                try:
                                    poll_data = await httpclient.read_json_limited(poll_resp)
                                except (aiohttp.ContentTypeError, ValueError):
                                    continue

                            if int(poll_data.get('retcode', -1)) != 0:
                                session['status'] = 'error'
                                session['error'] = poll_data.get('msg') or poll_data.get('message') or 'Poll failed'
                                return

                            payload = poll_data.get('data') or {}
                            try:
                                raw_status = int(payload.get('status', 0))
                            except (TypeError, ValueError):
                                raw_status = 0

                            if raw_status == 2:
                                appid = str(payload.get('bot_appid') or '').strip()
                                encrypted = str(payload.get('bot_encrypt_secret') or '').strip()
                                if not appid or not encrypted:
                                    session['status'] = 'error'
                                    session['error'] = 'Incomplete credential payload'
                                    return
                                try:
                                    session['secret'] = _decrypt_qqofficial_secret(
                                        encrypted,
                                        bind_key_bytes,
                                    )
                                except ValueError as exc:
                                    session['status'] = 'error'
                                    session['error'] = str(exc)
                                    return
                                session['appid'] = appid
                                # The scanner's OpenID is returned alongside the credentials —
                                # surfaced to the dashboard for audit / "bound by" display.
                                session['user_openid'] = str(payload.get('user_openid') or '').strip() or None
                                session['status'] = 'success'
                                return

                            if raw_status == 3:
                                session['status'] = 'expired'
                                session['error'] = 'QR code expired'
                                return
                            # status 0 / 1: still pending, continue polling

                        session['status'] = 'expired'
                        session['error'] = 'QR code expired'

                except asyncio.CancelledError:
                    return
                except Exception as e:
                    session['status'] = 'error'
                    session['error'] = str(e)

            task = _start_adapter_session_task(
                self.ap,
                run_qr_binding(),
                adapter='qqofficial',
                session_id=session_id,
                request_context=request_context,
            )
            if task is None:
                _qqofficial_sessions.pop(session_id, None)
                raise CredentialSetupError(429, 'Too many active credential exchanges')
            session['task'] = task

            # Wait up to 10s for the QR URL to be ready before responding.
            for _ in range(20):
                if session['qr_url'] or session['error']:
                    break
                await asyncio.sleep(0.5)

            if session['error']:
                task.cancel()
                raise CredentialSetupError(502, session['error'])

            if not session['qr_url']:
                task.cancel()
                session['status'] = 'error'
                session['error'] = 'Timeout waiting for QR code'
                raise CredentialSetupError(504, 'Timeout waiting for QR code')

            return {
                'session_id': session_id,
                'qr_url': session['qr_url'],
                'expire_at': session['expire_at'],
            }

        async def qqofficial_status(session_id: str, request_context: RequestContext) -> dict:
            """Poll QQ Official QR binding status."""
            _cleanup_expired_qqofficial_sessions()
            session = _get_owned_session(_qqofficial_sessions, session_id, request_context)
            if not session:
                raise CredentialSetupError(404, 'Session not found')

            data = {'status': session['status']}

            if session['status'] == 'success':
                data['appid'] = session['appid']
                data['secret'] = session['secret']
                if session.get('user_openid'):
                    data['user_openid'] = session['user_openid']
                _qqofficial_sessions.pop(session_id, None)
            elif session['status'] in ('error', 'expired'):
                data['error'] = session['error']
                _qqofficial_sessions.pop(session_id, None)

            return data

        async def qqofficial_cancel(session_id: str, request_context: RequestContext) -> dict:
            """Cancel and clean up a QQ Official QR binding session."""
            session = _pop_owned_session(_qqofficial_sessions, session_id, request_context)
            if session is None:
                raise CredentialSetupError(404, 'Session not found')
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return {}

        # ---- credential-session TTL enforcement ----
        #
        # Every store above holds a short-lived secret (app_secret,
        # client_secret, bot secret) between the platform handshake and the
        # caller persisting it. The per-route cleanups only run when another
        # request arrives, so an abandoned flow would keep its secret in memory
        # long past its validity window. This sweeper enforces the TTL on a
        # timer instead, and scrubs the secret fields as it evicts.

        def _credential_stores() -> list[tuple[dict, float]]:
            return [
                (_create_app_sessions, _SESSION_TTL),
                (_dingtalk_sessions, _DINGTALK_SESSION_TTL),
                (_wecombot_sessions, _WECOMBOT_SESSION_TTL),
                (_qqofficial_sessions, _QQOFFICIAL_SESSION_TTL),
            ]

        def _sweep_now() -> int:
            return _sweep_credential_sessions(_credential_stores())

        async def _credential_session_sweeper() -> None:
            """Enforce the session TTL on a timer, so it does not depend on traffic."""
            import asyncio as _asyncio

            while True:
                await _asyncio.sleep(_CREDENTIAL_SWEEP_INTERVAL_SECONDS)
                try:
                    _sweep_now()
                except Exception:  # pragma: no cover - a sweep must never kill the app
                    logging.getLogger(__name__).exception('credential session sweep failed')

        self._sweep_credential_sessions = _sweep_now
        # Some embeddings (notably test harnesses) provide a task manager without
        # create_task; the per-route cleanups still enforce the TTL there.
        create_task = getattr(self.ap.task_mgr, 'create_task', None)
        if callable(create_task):
            create_task(
                _credential_session_sweeper(),
                name='platform-credential-session-sweeper',
            )

        self.lark_start = lark_start
        self.lark_status = lark_status
        self.lark_cancel = lark_cancel
        self.weixin_start = weixin_start
        self.weixin_status = weixin_status
        self.weixin_cancel = weixin_cancel
        self.dingtalk_start = dingtalk_start
        self.dingtalk_status = dingtalk_status
        self.dingtalk_cancel = dingtalk_cancel
        self.wecombot_start = wecombot_start
        self.wecombot_status = wecombot_status
        self.wecombot_cancel = wecombot_cancel
        self.qqofficial_start = qqofficial_start
        self.qqofficial_status = qqofficial_status
        self.qqofficial_cancel = qqofficial_cancel


def get_credential_setup(ap) -> CredentialSetupService:
    service = getattr(ap, 'credential_setup_service', None)
    if service is None:
        service = CredentialSetupService(ap)
        ap.credential_setup_service = service
    return service
