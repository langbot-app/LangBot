# HumanTakeover Console Page - 后端 API 处理
from __future__ import annotations

import logging
import time
from typing import Any

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse

logger = logging.getLogger(__name__)


class ConsolePage(Page):
    """人工接管控制台页面后端。

    通过 self.plugin 访问插件共享状态(会话、消息、接管状态)。
    """

    async def handle_api(self, request: PageRequest) -> PageResponse:
        plugin = self.plugin
        endpoint = request.endpoint
        method = request.method
        body = request.body or {}

        try:
            # 先批量处理接管超时,保证返回数据准确
            await plugin.expire_timeouts()

            if endpoint == "/sessions" and method == "GET":
                return PageResponse.ok({"sessions": self._build_session_list(plugin)})

            if endpoint == "/messages" and method == "GET":
                session_key = self._get_param(request, "session_key")
                if not session_key:
                    return PageResponse.fail("session_key is required")
                # 打开会话即清除未处理红点
                await plugin.clear_unread(session_key)
                return PageResponse.ok(self._build_messages(plugin, session_key))

            if endpoint == "/clear_unread" and method == "POST":
                session_key = body.get("session_key", "")
                if not session_key:
                    return PageResponse.fail("session_key is required")
                await plugin.clear_unread(session_key)
                return PageResponse.ok({"cleared": True})

            if endpoint == "/takeover" and method == "POST":
                session_key = body.get("session_key", "")
                if not session_key:
                    return PageResponse.fail("session_key is required")
                ok = await plugin.set_takeover(session_key, True)
                if not ok:
                    return PageResponse.fail("session not found")
                return PageResponse.ok(self._takeover_state(plugin, session_key))

            if endpoint == "/takeover" and method == "DELETE":
                session_key = body.get("session_key", "")
                if not session_key:
                    return PageResponse.fail("session_key is required")
                ok = await plugin.set_takeover(session_key, False)
                if not ok:
                    return PageResponse.fail("session not found")
                return PageResponse.ok(self._takeover_state(plugin, session_key))

            if endpoint == "/takeover_status" and method == "GET":
                session_key = self._get_param(request, "session_key")
                if not session_key:
                    return PageResponse.fail("session_key is required")
                return PageResponse.ok(self._takeover_state(plugin, session_key))

            if endpoint == "/reply" and method == "POST":
                session_key = body.get("session_key", "")
                text = (body.get("text") or "").strip()
                image_base64 = body.get("image_base64") or ""
                file_base64 = body.get("file_base64") or ""
                file_name = body.get("file_name") or ""
                if not session_key:
                    return PageResponse.fail("session_key is required")
                if not text and not image_base64 and not file_base64:
                    return PageResponse.fail("text, image or file is required")
                ok, err = await plugin.human_send(
                    session_key,
                    text=text or None,
                    image_base64=image_base64 or None,
                    file_base64=file_base64 or None,
                    file_name=file_name or None,
                )
                if not ok:
                    return PageResponse.fail(err or "send failed")
                return PageResponse.ok(
                    {
                        "sent": True,
                        **self._takeover_state(plugin, session_key),
                    }
                )

            if endpoint == "/user_info" and method == "GET":
                session_key = self._get_param(request, "session_key")
                member_id = self._get_param(request, "member_id")
                return PageResponse.ok(
                    await self._user_info(plugin, session_key, member_id)
                )

            if endpoint == "/group_info" and method == "GET":
                session_key = self._get_param(request, "session_key")
                return PageResponse.ok(await self._group_info(plugin, session_key))

            if endpoint == "/clear" and method == "DELETE":
                await plugin.clear_all()
                return PageResponse.ok({"cleared": True})

            return PageResponse.fail(f"Unknown: {method} {endpoint}")
        except Exception as e:  # noqa: BLE001
            logger.error("HumanTakeover ConsolePage error on %s %s: %s", method, endpoint, e)
            return PageResponse.fail(str(e))

    # ==================== 工具 ====================

    @staticmethod
    def _get_param(request: PageRequest, key: str) -> str:
        """从 body 或 endpoint 查询参数中获取值。"""
        body = request.body or {}
        if isinstance(body, dict) and body.get(key):
            return str(body.get(key))
        # 兼容前端将参数放到 body 的情况
        return ""

    def _build_session_list(self, plugin) -> list[dict[str, Any]]:
        result = []
        for key, sess in plugin.sessions.items():
            takeover = sess.get("takeover", {})
            active = plugin.is_taken_over(key)
            result.append(
                {
                    "session_key": key,
                    "type": sess.get("type"),
                    "target_id": sess.get("target_id"),
                    "name": sess.get("name") or sess.get("target_id"),
                    "last_msg_at": sess.get("last_msg_at", 0),
                    "last_msg_preview": sess.get("last_msg_preview", ""),
                    "member_count": len(sess.get("members", {})),
                    "takeover_active": active,
                    "takeover_remaining": plugin.takeover_remaining(key),
                    "unread": bool(sess.get("unread")),
                    "triggered_word": sess.get("triggered_word", ""),
                }
            )
        # 按最后消息时间倒序
        result.sort(key=lambda x: x.get("last_msg_at", 0), reverse=True)
        return result

    def _build_messages(self, plugin, session_key: str) -> dict[str, Any]:
        sess = plugin.sessions.get(session_key, {})
        msgs = plugin.messages.get(session_key, [])
        return {
            "session_key": session_key,
            "type": sess.get("type"),
            "name": sess.get("name") or sess.get("target_id"),
            "messages": msgs,
            "members": sess.get("members", {}),
            **self._takeover_state(plugin, session_key),
        }

    def _takeover_state(self, plugin, session_key: str) -> dict[str, Any]:
        return {
            "takeover_active": plugin.is_taken_over(session_key),
            "takeover_remaining": plugin.takeover_remaining(session_key),
            "takeover_timeout": plugin.get_takeover_timeout(),
        }

    async def _user_info(
        self, plugin, session_key: str, member_id: str | None
    ) -> dict[str, Any]:
        """返回可获取到的用户信息卡片(含所属 bot 适配器信息)。"""
        sess = plugin.sessions.get(session_key, {})
        bot_uuid = sess.get("bot_uuid")
        # 优先使用收消息时缓存的适配器,避免调试环境 bot 离线时反复请求报错
        adapter = sess.get("adapter") or None
        bot_name = None
        if bot_uuid and not adapter:
            try:
                bot_info = await plugin.get_bot_info(bot_uuid)
                adapter = bot_info.get("adapter")
                bot_name = bot_info.get("name")
            except Exception as e:  # noqa: BLE001
                logger.warning("HumanTakeover get_bot_info failed: %s", e)

        if sess.get("type") == "group" and member_id:
            members = sess.get("members", {})
            name = members.get(str(member_id), str(member_id))
            return {
                "type": "user",
                "id": str(member_id),
                "name": name,
                "from_group": sess.get("name"),
                "group_id": sess.get("target_id"),
                "adapter": adapter,
                "bot_name": bot_name,
            }
        # 私聊用户
        return {
            "type": "user",
            "id": sess.get("target_id"),
            "name": sess.get("name"),
            "from_group": None,
            "group_id": None,
            "adapter": adapter,
            "bot_name": bot_name,
        }

    async def _group_info(self, plugin, session_key: str) -> dict[str, Any]:
        """返回群聊信息卡片(含成员列表)。"""
        sess = plugin.sessions.get(session_key, {})
        info: dict[str, Any] = {
            "type": "group",
            "id": sess.get("target_id"),
            "name": sess.get("name"),
            "member_count": len(sess.get("members", {})),
            "members": [
                {"id": mid, "name": mname}
                for mid, mname in sess.get("members", {}).items()
            ],
            "bot_uuid": sess.get("bot_uuid"),
        }
        # 尝试补充 bot 信息
        bot_uuid = sess.get("bot_uuid")
        # 优先使用缓存适配器
        cached_adapter = sess.get("adapter")
        if cached_adapter:
            info["adapter"] = cached_adapter
        if bot_uuid and not cached_adapter:
            try:
                bot_info = await plugin.get_bot_info(bot_uuid)
                info["bot_name"] = bot_info.get("name")
                info["adapter"] = bot_info.get("adapter")
            except Exception as e:  # noqa: BLE001
                logger.warning("HumanTakeover get_bot_info failed: %s", e)
        return info
