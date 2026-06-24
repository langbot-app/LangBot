import quart
import mimetypes
import asyncio
from ... import group
from langbot.pkg.utils import importutil


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


@group.group_class('adapters', '/api/v1/platform/adapters')
class AdaptersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'])
        async def _() -> str:
            return self.success(data={'adapters': self.ap.platform_mgr.get_available_adapters_info()})

        @self.route('/<adapter_name>', methods=['GET'])
        async def _(adapter_name: str) -> str:
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

        @self.route('/dingtalk/human-input-card-template', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> quart.Response:
            filename = 'dingtalk_human_input_card.json'
            response = quart.Response(
                importutil.read_resource_file_bytes(f'templates/{filename}'), mimetype='application/json'
            )
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return response

        # In-memory session store for active registrations
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

        @self.route('/lark/create-app', methods=['POST'])
        async def _() -> str:
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

            task = asyncio.create_task(run_registration())
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
                return self.http_status(504, -1, 'Timeout waiting for QR code')

            return self.success(
                data={
                    'session_id': session_id,
                    'qr_url': session['qr_url'],
                    'expire_at': session['expire_at'],
                }
            )

        @self.route('/lark/create-app/status/<session_id>', methods=['GET'])
        async def _(session_id: str) -> str:
            """Poll registration status."""
            session = _create_app_sessions.get(session_id)
            if not session:
                return self.http_status(404, -1, 'Session not found')

            data = {'status': session['status']}

            if session['status'] == 'success':
                data['app_id'] = session['app_id']
                data['app_secret'] = session['app_secret']
                _create_app_sessions.pop(session_id, None)
            elif session['status'] == 'error':
                data['error'] = session['error']
                _create_app_sessions.pop(session_id, None)

            return self.success(data=data)

        @self.route('/lark/create-app/<session_id>', methods=['DELETE'])
        async def _(session_id: str) -> str:
            """Cancel and clean up a registration session."""
            session = _create_app_sessions.pop(session_id, None)
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return self.success(data={})

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

        @self.route('/weixin/login', methods=['POST'])
        async def _() -> str:
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

            task = asyncio.create_task(run_login())
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
                return self.http_status(504, -1, 'Timeout waiting for QR code')

            return self.success(
                data={
                    'session_id': session_id,
                    'qr_data_url': session['qr_data_url'],
                    'expire_at': session['expire_at'],
                }
            )

        @self.route('/weixin/login/status/<session_id>', methods=['GET'])
        async def _(session_id: str) -> str:
            """Poll WeChat login status."""
            session = _weixin_login_sessions.get(session_id)
            if not session:
                return self.http_status(404, -1, 'Session not found')

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

            return self.success(data=data)

        @self.route('/weixin/login/<session_id>', methods=['DELETE'])
        async def _(session_id: str) -> str:
            """Cancel and clean up a WeChat login session."""
            session = _weixin_login_sessions.pop(session_id, None)
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return self.success(data={})

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

        @self.route('/dingtalk/create-app', methods=['POST'])
        async def _() -> str:
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
                                data = await resp.json()
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
                                data = await resp.json()
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
                                    poll_data = await poll_resp.json()
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

            task = asyncio.create_task(run_device_flow())
            session['task'] = task

            # Wait for QR code to be ready (max 10 seconds)
            for _ in range(20):
                if session['qr_url'] or session['error']:
                    break
                await asyncio.sleep(0.5)

            if session['error']:
                task.cancel()
                return self.http_status(502, -1, session['error'])

            if not session['qr_url']:
                task.cancel()
                session['status'] = 'error'
                session['error'] = 'Timeout waiting for QR code'
                return self.http_status(504, -1, 'Timeout waiting for QR code')

            return self.success(
                data={
                    'session_id': session_id,
                    'qr_url': session['qr_url'],
                    'expire_at': session['expire_at'],
                }
            )

        @self.route('/dingtalk/create-app/status/<session_id>', methods=['GET'])
        async def _(session_id: str) -> str:
            """Poll DingTalk Device Flow status."""
            _cleanup_expired_dingtalk_sessions()
            session = _dingtalk_sessions.get(session_id)
            if not session:
                return self.http_status(404, -1, 'Session not found')

            data = {'status': session['status']}

            if session['status'] == 'success':
                data['client_id'] = session['client_id']
                data['client_secret'] = session['client_secret']
                _dingtalk_sessions.pop(session_id, None)
            elif session['status'] == 'error':
                data['error'] = session['error']
                _dingtalk_sessions.pop(session_id, None)

            return self.success(data=data)

        @self.route('/dingtalk/create-app/<session_id>', methods=['DELETE'])
        async def _(session_id: str) -> str:
            """Cancel and clean up a DingTalk Device Flow session."""
            session = _dingtalk_sessions.pop(session_id, None)
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return self.success(data={})

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

        @self.route('/wecombot/create-bot', methods=['POST'])
        async def _() -> str:
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
                                data = await resp.json()
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
                                    poll_data = await poll_resp.json()
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

            task = asyncio.create_task(run_qr_flow())
            session['task'] = task

            # Wait for QR code to be ready (max 10 seconds)
            for _ in range(20):
                if session['qr_url'] or session['error']:
                    break
                await asyncio.sleep(0.5)

            if session['error']:
                task.cancel()
                return self.http_status(502, -1, session['error'])

            if not session['qr_url']:
                task.cancel()
                session['status'] = 'error'
                session['error'] = 'Timeout waiting for QR code'
                return self.http_status(504, -1, 'Timeout waiting for QR code')

            return self.success(
                data={
                    'session_id': session_id,
                    'qr_url': session['qr_url'],
                    'expire_at': session['expire_at'],
                }
            )

        @self.route('/wecombot/create-bot/status/<session_id>', methods=['GET'])
        async def _(session_id: str) -> str:
            """Poll WeComBot creation status."""
            _cleanup_expired_wecombot_sessions()
            session = _wecombot_sessions.get(session_id)
            if not session:
                return self.http_status(404, -1, 'Session not found')

            data = {'status': session['status']}

            if session['status'] == 'success':
                data['botid'] = session['botid']
                data['secret'] = session['secret']
                _wecombot_sessions.pop(session_id, None)
            elif session['status'] == 'error':
                data['error'] = session['error']
                _wecombot_sessions.pop(session_id, None)

            return self.success(data=data)

        @self.route('/wecombot/create-bot/<session_id>', methods=['DELETE'])
        async def _(session_id: str) -> str:
            """Cancel and clean up a WeComBot creation session."""
            session = _wecombot_sessions.pop(session_id, None)
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return self.success(data={})

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

        @self.route('/qqofficial/bind', methods=['POST'])
        async def _() -> str:
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
                                data = await resp.json(content_type=None)
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
                                    poll_data = await poll_resp.json(content_type=None)
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

            task = asyncio.create_task(run_qr_binding())
            session['task'] = task

            # Wait up to 10s for the QR URL to be ready before responding.
            for _ in range(20):
                if session['qr_url'] or session['error']:
                    break
                await asyncio.sleep(0.5)

            if session['error']:
                task.cancel()
                return self.http_status(502, -1, session['error'])

            if not session['qr_url']:
                task.cancel()
                session['status'] = 'error'
                session['error'] = 'Timeout waiting for QR code'
                return self.http_status(504, -1, 'Timeout waiting for QR code')

            return self.success(
                data={
                    'session_id': session_id,
                    'qr_url': session['qr_url'],
                    'expire_at': session['expire_at'],
                }
            )

        @self.route('/qqofficial/bind/status/<session_id>', methods=['GET'])
        async def _(session_id: str) -> str:
            """Poll QQ Official QR binding status."""
            _cleanup_expired_qqofficial_sessions()
            session = _qqofficial_sessions.get(session_id)
            if not session:
                return self.http_status(404, -1, 'Session not found')

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

            return self.success(data=data)

        @self.route('/qqofficial/bind/<session_id>', methods=['DELETE'])
        async def _(session_id: str) -> str:
            """Cancel and clean up a QQ Official QR binding session."""
            session = _qqofficial_sessions.pop(session_id, None)
            if session and session.get('task') and not session['task'].done():
                session['task'].cancel()
            return self.success(data={})
