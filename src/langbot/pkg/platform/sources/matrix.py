from __future__ import annotations

import typing
import asyncio
import traceback
import base64
import json

import nio

from langbot.pkg.utils import httpclient
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class MatrixMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, client: nio.AsyncClient) -> list[dict]:
        components = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                components.append({'type': 'text', 'text': component.text})
            elif isinstance(component, platform_message.Image):
                image_bytes = None
                if component.base64:
                    b64_data = component.base64
                    if ';base64,' in b64_data:
                        b64_data = b64_data.split(';base64,', 1)[1]
                    image_bytes = base64.b64decode(b64_data)
                elif component.url:
                    session = httpclient.get_session()
                    async with session.get(component.url) as response:
                        image_bytes = await response.read()
                elif component.path:
                    with open(component.path, 'rb') as f:
                        image_bytes = f.read()
                if image_bytes:
                    resp = await client.upload(image_bytes, content_type='image/png')
                    if isinstance(resp, nio.UploadResponse):
                        components.append({'type': 'image', 'mxc_url': resp.content_uri})
            elif isinstance(component, platform_message.File):
                file_bytes = None
                if component.base64:
                    b64_data = component.base64
                    if ';base64,' in b64_data:
                        b64_data = b64_data.split(';base64,', 1)[1]
                    file_bytes = base64.b64decode(b64_data)
                elif component.url:
                    session = httpclient.get_session()
                    async with session.get(component.url) as response:
                        file_bytes = await response.read()
                elif component.path:
                    with open(component.path, 'rb') as f:
                        file_bytes = f.read()
                if file_bytes:
                    file_name = getattr(component, 'name', None) or 'file'
                    resp = await client.upload(file_bytes, content_type='application/octet-stream', filename=file_name)
                    if isinstance(resp, nio.UploadResponse):
                        components.append({
                            'type': 'file',
                            'mxc_url': resp.content_uri,
                            'filename': file_name,
                            'size': len(file_bytes),
                        })
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    components.extend(await MatrixMessageConverter.yiri2target(node.message_chain, client))
        return components

    @staticmethod
    async def target2yiri(event: nio.RoomMessageText | nio.RoomMessageImage, client: nio.AsyncClient, bot_user_id: str):
        message_components = []

        if isinstance(event, nio.RoomMessageText):
            text = event.body
            if bot_user_id and bot_user_id in text:
                message_components.append(platform_message.At(target=bot_user_id))
                text = text.replace(bot_user_id, '').strip()
            message_components.append(platform_message.Plain(text=text))

        elif isinstance(event, nio.RoomMessageImage):
            mxc_url = event.url
            if mxc_url:
                resp = await client.download(mxc_url)
                if isinstance(resp, nio.DownloadResponse):
                    b64 = base64.b64encode(resp.body).decode('utf-8')
                    content_type = resp.content_type or 'image/png'
                    message_components.append(
                        platform_message.Image(base64=f'data:{content_type};base64,{b64}')
                    )
            if event.body:
                message_components.append(platform_message.Plain(text=event.body))

        return platform_message.MessageChain(message_components)


class MatrixEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(
        event: nio.RoomMessageText | nio.RoomMessageImage,
        room: nio.MatrixRoom,
        client: nio.AsyncClient,
        bot_user_id: str,
        bridge_user_ids: list[str] | None = None,
    ):
        lb_message = await MatrixMessageConverter.target2yiri(event, client, bot_user_id)

        # Determine if this is a direct/private chat or a group chat.
        # Exclude bot itself and bridge bots, count remaining real users.
        exclude_ids = {bot_user_id}
        if bridge_user_ids:
            exclude_ids.update(bridge_user_ids)
        real_users = [uid for uid in room.users if uid not in exclude_ids]
        is_direct = len(real_users) <= 1

        if is_direct:
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.sender,
                    nickname=room.user_name(event.sender) or event.sender,
                    remark='',
                ),
                message_chain=lb_message,
                time=event.server_timestamp / 1000.0,
                source_platform_object={'event': event, 'room': room},
            )
        else:
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.sender,
                    member_name=room.user_name(event.sender) or event.sender,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=room.room_id,
                        name=room.display_name or room.room_id,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=lb_message,
                time=event.server_timestamp / 1000.0,
                source_platform_object={'event': event, 'room': room},
            )


class BridgeState:
    """Per-bridge runtime state."""

    def __init__(self, user_id: str, login_command: str, logout_command: str, success_keyword: str, check_command: str):
        self.user_id = user_id
        self.login_command = login_command
        self.logout_command = logout_command
        self.success_keyword = success_keyword
        self.check_command = check_command or login_command
        self.logged_in = False
        self.dm_room_id: str | None = None
        self.login_task: asyncio.Task | None = None
        self.check_task: asyncio.Task | None = None
        self.check_responded = False


class MatrixAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    client: typing.Any = None
    message_converter: MatrixMessageConverter = MatrixMessageConverter()
    event_converter: MatrixEventConverter = MatrixEventConverter()
    config: dict
    listeners: typing.Dict[typing.Type[platform_events.Event], typing.Callable] = {}
    _running: bool = False
    _initial_sync_done: bool = False
    _bridges: list = []

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        homeserver_url = config.get('homeserver_url', '')
        access_token = config.get('access_token', '')
        user_id = config.get('user_id', '')

        if not homeserver_url or not access_token or not user_id:
            raise ValueError('Matrix 机器人缺少必要配置项 (homeserver_url, user_id, access_token)')

        client = nio.AsyncClient(homeserver_url, user_id)
        client.access_token = access_token
        client.user_id = user_id

        super().__init__(
            config=config,
            logger=logger,
            bot_account_id=user_id,
            client=client,
            listeners={},
        )

        # Parse bridges config AFTER super().__init__() to avoid Pydantic resetting _bridges
        self._bridges = []
        bridges_raw = config.get('bridges', '')
        if bridges_raw:
            if isinstance(bridges_raw, str):
                try:
                    bridges_list = json.loads(bridges_raw)
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(f'bridges 配置 JSON 解析失败: {e}\n原始值: {bridges_raw}')
            else:
                bridges_list = bridges_raw
            for b in bridges_list:
                if isinstance(b, dict) and b.get('user_id', '').strip():
                    self._bridges.append(BridgeState(
                        user_id=b['user_id'].strip(),
                        login_command=b.get('login_command', '').strip(),
                        logout_command=b.get('logout_command', '').strip(),
                        success_keyword=b.get('success_keyword', 'Successfully logged in').strip(),
                        check_command=b.get('check_command', '').strip(),
                    ))
        # Backward compatibility: old single-bridge config
        if not self._bridges:
            old_user_id = config.get('bridge_user_id', '').strip()
            old_command = config.get('bridge_login_command', '').strip()
            old_keyword = config.get('bridge_login_success_keyword', 'Successfully logged in').strip()
            old_check = config.get('bridge_check_command', '').strip()
            old_logout = config.get('bridge_logout_command', '').strip()
            if old_user_id:
                self._bridges.append(BridgeState(
                    user_id=old_user_id,
                    login_command=old_command,
                    logout_command=old_logout,
                    success_keyword=old_keyword,
                    check_command=old_check,
                ))

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        components = await self.message_converter.yiri2target(message, self.client)
        for component in components:
            await self._send_component(target_id, component)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        source_obj = message_source.source_platform_object
        room_id = source_obj['room'].room_id
        components = await self.message_converter.yiri2target(message, self.client)

        for component in components:
            if quote_origin:
                original_event = source_obj['event']
                await self._send_component(room_id, component, reply_to=original_event.event_id)
            else:
                await self._send_component(room_id, component)

    async def _send_component(self, room_id: str, component: dict, reply_to: str | None = None):
        content = {}
        if component['type'] == 'text':
            content = {
                'msgtype': 'm.text',
                'body': component['text'],
            }
        elif component['type'] == 'image':
            content = {
                'msgtype': 'm.image',
                'body': 'image.png',
                'url': component['mxc_url'],
            }
        elif component['type'] == 'file':
            content = {
                'msgtype': 'm.file',
                'body': component.get('filename', 'file'),
                'url': component['mxc_url'],
                'info': {'size': component.get('size', 0)},
            }

        if reply_to and content:
            content['m.relates_to'] = {
                'm.in_reply_to': {'event_id': reply_to},
            }

        if content:
            await self.client.room_send(
                room_id=room_id,
                message_type='m.room.message',
                content=content,
            )

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        self.listeners[event_type] = callback

    async def run_async(self):
        self._running = True
        await self.logger.info('Matrix adapter starting...')

        # Debug: log bridge parsing result
        bridges_raw = self.config.get('bridges', '')
        await self.logger.debug(f'bridges config raw: type={type(bridges_raw).__name__}, repr={repr(bridges_raw)}')
        await self.logger.debug(f'parsed _bridges count: {len(self._bridges)}, ids: {[b.user_id for b in self._bridges]}')

        # Collect all bridge bot user IDs for filtering
        _bridge_user_ids = [b.user_id for b in self._bridges]
        _bridge_user_id_set = set(_bridge_user_ids)

        # Auto-join invited rooms
        async def on_invite(room: nio.MatrixRoom, event: nio.InviteMemberEvent):
            if event.membership == 'invite' and event.state_key == self.client.user_id:
                await self.client.join(room.room_id)
                await self.logger.debug(f'Auto-joined room: {room.display_name or room.room_id}')

        self.client.add_event_callback(on_invite, nio.InviteMemberEvent)

        # Handle text messages
        async def on_message(room: nio.MatrixRoom, event: nio.RoomMessageText):
            if not self._initial_sync_done:
                return
            if event.sender == self.client.user_id:
                return

            # Admin commands (from any non-bridge user)
            if event.sender not in _bridge_user_id_set:
                body = (event.body or '').strip()
                if body == '!relogin':
                    await self._handle_relogin_command(room.room_id)
                    return
                if body == '!status':
                    await self._handle_status_command(room.room_id)
                    return

            if event.sender in _bridge_user_id_set:
                return
            try:
                lb_event = await self.event_converter.target2yiri(event, room, self.client, self.bot_account_id, _bridge_user_ids)
                if type(lb_event) in self.listeners:
                    result = self.listeners[type(lb_event)](lb_event, self)
                    if asyncio.iscoroutine(result):
                        await result
            except Exception:
                await self.logger.error(f'Error handling Matrix message: {traceback.format_exc()}')

        self.client.add_event_callback(on_message, nio.RoomMessageText)

        # Handle image messages
        async def on_image(room: nio.MatrixRoom, event: nio.RoomMessageImage):
            if not self._initial_sync_done:
                return
            if event.sender == self.client.user_id:
                return
            if event.sender in _bridge_user_id_set:
                return
            try:
                lb_event = await self.event_converter.target2yiri(event, room, self.client, self.bot_account_id, _bridge_user_ids)
                if type(lb_event) in self.listeners:
                    result = self.listeners[type(lb_event)](lb_event, self)
                    if asyncio.iscoroutine(result):
                        await result
            except Exception:
                await self.logger.error(f'Error handling Matrix image: {traceback.format_exc()}')

        self.client.add_event_callback(on_image, nio.RoomMessageImage)

        # Set up bridge-specific callbacks for each bridge
        _disconnect_keywords = ['disconnected', 'logged out', 'connection lost', 'session expired', 'token expired']

        for bridge in self._bridges:
            # Login success detection (notice)
            async def on_bridge_notice(room: nio.MatrixRoom, event: nio.RoomMessageNotice, _b=bridge):
                if not self._initial_sync_done:
                    return
                if event.sender != _b.user_id:
                    return
                _b.check_responded = True
                if _b.success_keyword in (event.body or ''):
                    _b.logged_in = True
                    await self.logger.info(f'[{_b.user_id}] Bridge login succeeded.')
                # Disconnect detection
                body_lower = (event.body or '').lower()
                for kw in _disconnect_keywords:
                    if kw in body_lower and _b.logged_in:
                        _b.logged_in = False
                        await self.logger.info(f'[{_b.user_id}] Bridge 账号掉线 (检测到: "{kw}"), 将自动重新登录...')
                        self._restart_bridge_login(_b)
                        break

            self.client.add_event_callback(on_bridge_notice, nio.RoomMessageNotice)

            # Login success + disconnect detection (text)
            async def on_bridge_text(room: nio.MatrixRoom, event: nio.RoomMessageText, _b=bridge):
                if not self._initial_sync_done:
                    return
                if event.sender != _b.user_id:
                    return
                _b.check_responded = True
                if _b.success_keyword in (event.body or ''):
                    _b.logged_in = True
                    await self.logger.info(f'[{_b.user_id}] Bridge login succeeded.')
                body_lower = (event.body or '').lower()
                for kw in _disconnect_keywords:
                    if kw in body_lower and _b.logged_in:
                        _b.logged_in = False
                        await self.logger.info(f'[{_b.user_id}] Bridge 账号掉线 (检测到: "{kw}"), 将自动重新登录...')
                        self._restart_bridge_login(_b)
                        break

            self.client.add_event_callback(on_bridge_text, nio.RoomMessageText)

            # QR code image forwarding
            async def on_bridge_image(room: nio.MatrixRoom, event: nio.RoomMessageImage, _b=bridge):
                if not self._initial_sync_done:
                    return
                if event.sender != _b.user_id:
                    return
                mxc_url = event.url
                if not mxc_url:
                    return
                try:
                    resp = await self.client.download(mxc_url)
                    if isinstance(resp, nio.DownloadResponse):
                        b64 = base64.b64encode(resp.body).decode('utf-8')
                        content_type = resp.content_type or 'image/png'
                        await self.logger.info(
                            f'[{_b.user_id}] Bridge 发送了二维码，请扫码登录:',
                            images=[platform_message.Image(base64=f'data:{content_type};base64,{b64}')],
                        )
                except Exception:
                    await self.logger.error(f'[{_b.user_id}] Failed to download bridge QR image: {traceback.format_exc()}')

            self.client.add_event_callback(on_bridge_image, nio.RoomMessageImage)

        await self.logger.debug('Matrix adapter running, starting sync...')

        # Initial sync to skip old messages
        resp = await self.client.sync(timeout=10000)
        if isinstance(resp, nio.SyncResponse):
            await self.logger.debug(f'Matrix initial sync done, next_batch: {resp.next_batch}')
        self._initial_sync_done = True

        # Display account info
        display_name = self.client.user_id
        try:
            profile_resp = await self.client.get_displayname(self.client.user_id)
            if isinstance(profile_resp, nio.ProfileGetDisplayNameResponse) and profile_resp.displayname:
                display_name = profile_resp.displayname
        except Exception:
            pass
        joined_rooms = len(self.client.rooms)
        homeserver = self.config.get('homeserver_url', '')
        bridge_info = ''
        if self._bridges:
            bridge_names = ', '.join(b.user_id for b in self._bridges)
            bridge_info = f' | 桥接: [{bridge_names}]'
        await self.logger.info(
            f'Matrix 账号: {display_name} ({self.client.user_id}) | '
            f'服务器: {homeserver} | 已加入 {joined_rooms} 个房间{bridge_info}'
        )

        # Start bridge login and status check tasks for each bridge
        for bridge in self._bridges:
            if bridge.login_command:
                await self.logger.info(
                    f'[{bridge.user_id}] Bridge login enabled (命令: "{bridge.login_command}", '
                    f'关键词: "{bridge.success_keyword}")'
                )
                bridge.login_task = asyncio.create_task(
                    self._periodic_bridge_login(bridge)
                )
                bridge.check_task = asyncio.create_task(
                    self._periodic_bridge_check(bridge)
                )
            else:
                await self.logger.debug(f'[{bridge.user_id}] Bridge login not configured (no login_command)')

        # Main sync loop
        while self._running:
            try:
                await self.client.sync(timeout=30000)
            except Exception:
                await self.logger.error(f'Matrix sync error: {traceback.format_exc()}')
                await asyncio.sleep(5)

    async def _periodic_bridge_login(self, bridge: BridgeState):
        """Periodically send login command to a bridge bot until login succeeds."""
        try:
            await self.logger.info(f'[{bridge.user_id}] Bridge login task started, looking for DM room...')
            dm_room_id = None
            for room_id, room in self.client.rooms.items():
                if room.member_count == 2 and bridge.user_id in [m for m in room.users]:
                    dm_room_id = room_id
                    break

            if not dm_room_id:
                resp = await self.client.room_create(
                    is_direct=True,
                    invite=[bridge.user_id],
                )
                if isinstance(resp, nio.RoomCreateResponse):
                    dm_room_id = resp.room_id
                    await self.logger.debug(f'[{bridge.user_id}] Created DM room: {dm_room_id}')
                else:
                    await self.logger.error(f'[{bridge.user_id}] Failed to create DM room: {resp}')
                    return

            bridge.dm_room_id = dm_room_id

            # Force logout first on every adapter start
            logout_cmd = bridge.logout_command or bridge.login_command.replace('login', 'logout')
            await self.logger.info(f'[{bridge.user_id}] 强制登出: "{logout_cmd}"')
            await self.client.room_send(
                room_id=dm_room_id,
                message_type='m.room.message',
                content={'msgtype': 'm.text', 'body': logout_cmd},
            )
            await asyncio.sleep(3)

            while self._running and not bridge.logged_in:
                await self.logger.debug(f'[{bridge.user_id}] Sending "{bridge.login_command}" in room {dm_room_id}')
                await self.client.room_send(
                    room_id=dm_room_id,
                    message_type='m.room.message',
                    content={'msgtype': 'm.text', 'body': bridge.login_command},
                )
                for _ in range(60):
                    if not self._running or bridge.logged_in:
                        break
                    await asyncio.sleep(1)

            if bridge.logged_in:
                await self.logger.debug(f'[{bridge.user_id}] Bridge login confirmed, periodic login stopped.')
        except asyncio.CancelledError:
            pass
        except Exception:
            await self.logger.error(f'[{bridge.user_id}] Bridge periodic login error: {traceback.format_exc()}')

    def _restart_bridge_login(self, bridge: BridgeState):
        """Cancel existing login task and start a new one."""
        if bridge.login_task and not bridge.login_task.done():
            bridge.login_task.cancel()
        bridge.login_task = asyncio.create_task(
            self._periodic_bridge_login(bridge)
        )

    async def _periodic_bridge_check(self, bridge: BridgeState):
        """Periodically check a bridge's login status."""
        try:
            while self._running and not bridge.logged_in:
                await asyncio.sleep(5)

            check_interval = 300  # 5 minutes
            response_timeout = 30
            await self.logger.debug(f'[{bridge.user_id}] Bridge status check started (interval: {check_interval}s)')

            while self._running:
                for _ in range(check_interval):
                    if not self._running:
                        return
                    await asyncio.sleep(1)

                if not bridge.logged_in or not bridge.dm_room_id:
                    continue

                try:
                    bridge.check_responded = False
                    await self.client.room_send(
                        room_id=bridge.dm_room_id,
                        message_type='m.room.message',
                        content={'msgtype': 'm.text', 'body': bridge.check_command},
                    )
                    await self.logger.debug(f'[{bridge.user_id}] Bridge status check: sent "{bridge.check_command}"')

                    for _ in range(response_timeout):
                        if bridge.check_responded or not self._running:
                            break
                        await asyncio.sleep(1)

                    if bridge.check_responded:
                        await self.logger.debug(f'[{bridge.user_id}] Bridge status check: OK')
                    else:
                        await self.logger.info(f'[{bridge.user_id}] Bridge status check: 无响应, 可能已掉线, 尝试重新登录...')
                        bridge.logged_in = False
                        self._restart_bridge_login(bridge)
                except Exception:
                    await self.logger.error(f'[{bridge.user_id}] Bridge status check error: {traceback.format_exc()}')
        except asyncio.CancelledError:
            pass
        except Exception:
            await self.logger.error(f'[{bridge.user_id}] Bridge status check fatal error: {traceback.format_exc()}')

    async def _handle_relogin_command(self, room_id: str):
        """Handle !relogin command: logout then re-login all bridges."""
        if not self._bridges:
            await self.client.room_send(
                room_id=room_id,
                message_type='m.room.message',
                content={'msgtype': 'm.text', 'body': '没有配置任何桥。'},
            )
            return

        lines = ['开始重新登录所有桥...']
        for bridge in self._bridges:
            if not bridge.login_command or not bridge.dm_room_id:
                lines.append(f'[{bridge.user_id}] 跳过（未配置登录命令或无DM房间）')
                continue

            # Use configured logout command, fallback to deriving from login command
                logout_cmd = bridge.logout_command or bridge.login_command.replace('login', 'logout')
            lines.append(f'[{bridge.user_id}] 发送 "{logout_cmd}"...')

            # Cancel existing tasks
            if bridge.login_task and not bridge.login_task.done():
                bridge.login_task.cancel()
            if bridge.check_task and not bridge.check_task.done():
                bridge.check_task.cancel()

            # Send logout
            try:
                await self.client.room_send(
                    room_id=bridge.dm_room_id,
                    message_type='m.room.message',
                    content={'msgtype': 'm.text', 'body': logout_cmd},
                )
            except Exception as e:
                lines.append(f'[{bridge.user_id}] logout 发送失败: {e}')

            await asyncio.sleep(2)

            # Reset state and restart login
            bridge.logged_in = False
            self._restart_bridge_login(bridge)
            lines.append(f'[{bridge.user_id}] 已触发重新登录')

        await self.client.room_send(
            room_id=room_id,
            message_type='m.room.message',
            content={'msgtype': 'm.text', 'body': '\n'.join(lines)},
        )

    async def _handle_status_command(self, room_id: str):
        """Handle !status command: show bridge states."""
        if not self._bridges:
            await self.client.room_send(
                room_id=room_id,
                message_type='m.room.message',
                content={'msgtype': 'm.text', 'body': '没有配置任何桥。'},
            )
            return

        lines = ['桥状态:']
        for bridge in self._bridges:
            status = '已登录 ✓' if bridge.logged_in else '未登录 ✗'
            dm = bridge.dm_room_id or '无'
            lines.append(f'• {bridge.user_id}: {status} (DM: {dm})')
        await self.client.room_send(
            room_id=room_id,
            message_type='m.room.message',
            content={'msgtype': 'm.text', 'body': '\n'.join(lines)},
        )

    async def kill(self) -> bool:
        self._running = False
        for bridge in self._bridges:
            if bridge.login_task and not bridge.login_task.done():
                bridge.login_task.cancel()
            if bridge.check_task and not bridge.check_task.done():
                bridge.check_task.cancel()
        if self.client:
            await self.client.close()
        await self.logger.debug('Matrix adapter stopped')
        return True

    async def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        if event_type in self.listeners:
            del self.listeners[event_type]
