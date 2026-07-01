import quart
import mimetypes
import asyncio
from ... import group
from langbot.pkg.utils import importutil


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
        # Itchat WeChat QR Code Login
        # -----------------------------------------------------------------------

        _itchat_login_sessions: dict = {}
        _ITCHAT_SESSION_TTL = 600  # 10 minutes (allows multiple QR regenerations)

        def _cleanup_expired_itchat_sessions():
            import time

            now = time.time()
            expired = [
                sid for sid, s in _itchat_login_sessions.items() if now - s.get('created_at', 0) > _ITCHAT_SESSION_TTL
            ]
            for sid in expired:
                session = _itchat_login_sessions.pop(sid, None)
                if session:
                    core = session.get('core')
                    if core:
                        try:
                            core.alive = False
                            core.isLogging = False
                        except Exception:
                            pass

        @self.route('/itchat/login', methods=['POST'])
        async def _() -> str:
            """Start itchat WeChat QR code login. Returns session_id + QR code data URL."""
            import uuid
            import time
            import base64
            import threading

            _cleanup_expired_itchat_sessions()

            session_id = str(uuid.uuid4())
            loop = asyncio.get_running_loop()

            session = {
                'status': 'pending',
                'qr_data_url': None,
                'expire_at': None,
                'nickname': None,
                'error': None,
                'created_at': time.time(),
                'thread': None,
                'logged_in': threading.Event(),
                'core': None,
            }
            _itchat_login_sessions[session_id] = session

            def _run_itchat_login():
                try:
                    import os

                    from itchat.core import Core
                    from itchat.content import TEXT as _TEXT

                    for f in ('itchat.pkl', 'QR.png'):
                        try:
                            os.remove(f)
                        except OSError:
                            pass

                    _core = Core()
                    session['core'] = _core

                    def on_login():
                        try:
                            _core.get_friends(update=True)
                            user_info = _core.loginInfo.get('User', {})
                            nick = (
                                getattr(user_info, 'NickName', '') or user_info.get('NickName', '')
                                if isinstance(user_info, dict)
                                else 'unknown'
                            )
                            wxid = (
                                getattr(user_info, 'UserName', '') or user_info.get('UserName', '')
                                if isinstance(user_info, dict)
                                else ''
                            )
                        except Exception:
                            nick = 'unknown'
                            wxid = ''
                        session['nickname'] = nick
                        session['wxid'] = wxid
                        session['status'] = 'success'
                        session['logged_in'].set()
                        print(f'[itchat-login] Login success: {nick}', flush=True)
                        # Dump login status so the adapter can hot-reload it
                        try:
                            _core.dump_login_status('itchat.pkl')
                            print('[itchat-login] Session saved to itchat.pkl', flush=True)
                        except Exception:
                            pass
                        # Stop the message loop - we only needed the session for QR login
                        _core.alive = False

                    def on_qr(**kwargs):
                        qr_bytes = kwargs.get('qrcode', b'')
                        status = kwargs.get('status', '')
                        print(f'[itchat-login] QR callback: status={status}, bytes={len(qr_bytes)}', flush=True)
                        if status == '200':
                            return
                        # Only update QR image on new QR generation (status='0')
                        # or when status changes to '408' (timeout, QR may refresh)
                        if qr_bytes and status == '0':
                            b64 = base64.b64encode(qr_bytes).decode('utf-8')

                            def _update():
                                session['qr_data_url'] = f'data:image/png;base64,{b64}'
                                session['expire_at'] = time.time() + 120
                                session['status'] = 'waiting'

                            loop.call_soon_threadsafe(_update)

                    # Register a dummy text handler
                    @_core.msg_register([_TEXT])
                    def _dummy(msg):
                        pass

                    print('[itchat-login] Step 3: Calling auto_login...', flush=True)
                    _core.auto_login(
                        hotReload=False,
                        loginCallback=on_login,
                        qrCallback=on_qr,
                    )
                    print('[itchat-login] Step 4: auto_login returned, starting run...', flush=True)
                    _core.run(blockThread=True)
                    print('[itchat-login] Step 5: run() returned', flush=True)
                except SystemExit as e:
                    print(f'[itchat-login] SystemExit: {e}', flush=True)
                    session['status'] = 'error'
                    session['error'] = f'itchat exited: {e}'
                    session['logged_in'].set()
                except Exception as e:
                    import traceback

                    print(f'[itchat-login] Exception: {traceback.format_exc()}', flush=True)
                    session['status'] = 'error'
                    session['error'] = str(e)
                    session['logged_in'].set()

            t = threading.Thread(target=_run_itchat_login, daemon=True)
            t.start()
            session['thread'] = t

            # Wait for QR code to be ready (max 15 seconds)
            for _ in range(30):
                if session['qr_data_url'] or session['error'] or session['status'] == 'success':
                    break
                await asyncio.sleep(0.5)

            if session['error']:
                return self.http_status(502, -1, session['error'])

            if session['status'] == 'success':
                return self.success(
                    data={
                        'session_id': session_id,
                        'status': 'success',
                        'nickname': session['nickname'],
                    }
                )

            if not session['qr_data_url']:
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

        @self.route('/itchat/login/status/<session_id>', methods=['GET'])
        async def _(session_id: str) -> str:
            """Poll itchat login status."""
            session = _itchat_login_sessions.get(session_id)
            if not session:
                return self.http_status(404, -1, 'Session not found')

            data = {
                'status': session['status'],
                'qr_data_url': session['qr_data_url'],
                'expire_at': session['expire_at'],
            }

            if session['status'] == 'success':
                data['nickname'] = session.get('nickname', '')
                data['wxid'] = session.get('wxid', '')
                # Keep session alive (don't pop) - itchat thread keeps running
                # so the pickle file is valid for the adapter to reuse
            elif session['status'] == 'error':
                data['error'] = session['error']
                _itchat_login_sessions.pop(session_id, None)

            return self.success(data=data)

        @self.route('/itchat/login/<session_id>', methods=['DELETE'])
        async def _(session_id: str) -> str:
            """Cancel and clean up an itchat login session."""
            session = _itchat_login_sessions.pop(session_id, None)
            if session:
                core = session.get('core')
                if core:
                    try:
                        core.alive = False
                        core.isLogging = False
                    except Exception:
                        pass
                thread = session.get('thread')
                if thread and thread.is_alive():
                    # Thread is daemon, will die with the process
                    pass
            return self.success(data={})
