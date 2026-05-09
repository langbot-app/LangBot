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
            import io
            import base64

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
                    import qrcode as qr_lib

                    for _attempt in range(3):
                        qr_resp = await client.fetch_qrcode()
                        if not qr_resp.qrcode or not qr_resp.qrcode_img_content:
                            raise Exception('Failed to get QR code from server')

                        # Generate QR code image locally
                        qr = qr_lib.QRCode(error_correction=qr_lib.constants.ERROR_CORRECT_L)
                        qr.add_data(qr_resp.qrcode_img_content)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color='black', back_color='white')
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                        data_url = f'data:image/png;base64,{b64}'

                        def _update_qr():
                            session['qr_data_url'] = data_url
                            session['expire_at'] = time.time() + 480  # 8 minutes
                            session['status'] = 'waiting'

                        loop.call_soon_threadsafe(_update_qr)

                        # Poll for scan status
                        deadline = loop.time() + 180
                        while loop.time() < deadline:
                            try:
                                status_resp = await client.poll_qrcode_status(qr_resp.qrcode)
                            except Exception:
                                await asyncio.sleep(2)
                                continue

                            if status_resp.status == 'confirmed' and status_resp.bot_token:
                                session['status'] = 'success'
                                session['token'] = status_resp.bot_token
                                session['base_url'] = status_resp.baseurl or client.base_url
                                session['account_id'] = status_resp.ilink_bot_id or ''
                                return

                            if status_resp.status == 'expired':
                                break  # retry with new QR code

                            await asyncio.sleep(1)
                        else:
                            pass  # timeout, retry

                    # All retries exhausted
                    session['status'] = 'error'
                    session['error'] = 'QR code login failed: max retries exceeded'

                except Exception as e:
                    session['status'] = 'error'
                    session['error'] = str(e)
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

            data = {'status': session['status']}

            if session['status'] == 'success':
                data['token'] = session['token']
                data['base_url'] = session['base_url']
                data['account_id'] = session['account_id']
                _weixin_login_sessions.pop(session_id, None)
            elif session['status'] == 'error':
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
