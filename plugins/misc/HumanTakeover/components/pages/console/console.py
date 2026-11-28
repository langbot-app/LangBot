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
                label = ""
                if isinstance(body, dict):
                    label = str(body.get("label") or "")
                if label:
                    keys = set(await plugin.sessions_with_label(label))
                    return PageResponse.ok(
                        {"sessions": await self._build_session_list(plugin, keys)}
                    )
                return PageResponse.ok(
                    {"sessions": await self._build_session_list(plugin)}
                )

            if endpoint == "/messages" and method == "GET":
                session_key = self._get_param(request, "session_key")
                if not session_key:
                    return PageResponse.fail("session_key is required")
                # 打开会话即清除未处理红点
                await plugin.clear_unread(session_key)
                try:
                    limit = int(self._get_param(request, "limit") or 300) or 300
                except ValueError:
                    limit = 300
                before_ts = self._get_param(request, "before_ts") or None
                # 游标分页:默认返回最近一页;before_ts 请求更早的一页。
                # 300 条保留预算不变,避免一次性承载整段历史导致界面冻结。
                page = await plugin.history_page(
                    session_key, limit=limit, before_ts=before_ts
                )
                sess = plugin.sessions.get(session_key, {})
                store = await plugin.labels_store()
                member_labels = {
                    str(member_id): list(
                        (store.get(str(member_id)) or {}).get("labels", [])
                    )
                    for member_id in (sess.get("members") or {})
                }
                return PageResponse.ok(
                    {
                        "session_key": session_key,
                        "type": sess.get("type"),
                        "name": sess.get("name") or sess.get("target_id"),
                        "messages": page["messages"],
                        "members": sess.get("members", {}),
                        "member_labels": member_labels,
                        "has_more": page["has_more"],
                        "next_cursor": page["next_cursor"],
                        **self._takeover_state(plugin, session_key),
                    }
                )

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
                voice_base64 = body.get("voice_base64") or ""
                file_base64 = body.get("file_base64") or ""
                file_name = body.get("file_name") or ""
                quote_message_id = body.get("quote_message_id") or ""
                quoted_content = body.get("quoted_content") or ""
                if not session_key:
                    return PageResponse.fail("session_key is required")
                if not (text or image_base64 or voice_base64 or file_base64):
                    return PageResponse.fail(
                        "text, image, voice, file or quote is required"
                    )
                ok, err = await plugin.human_send(
                    session_key,
                    text=text or None,
                    image_base64=image_base64 or None,
                    voice_base64=voice_base64 or None,
                    file_base64=file_base64 or None,
                    file_name=file_name or None,
                    quote_message_id=quote_message_id or None,
                    quoted_content=quoted_content or None,
                )
                if not ok:
                    return PageResponse.fail(err or "send failed")
                return PageResponse.ok(
                    {
                        "sent": True,
                        **self._takeover_state(plugin, session_key),
                    }
                )

            if endpoint == "/recall" and method == "POST":
                session_key = body.get("session_key", "")
                message_id = body.get("message_id", "")
                if not session_key:
                    return PageResponse.fail("session_key is required")
                if not message_id:
                    return PageResponse.fail("message_id is required")
                ok, err = await plugin.recall_message(session_key, str(message_id))
                if not ok:
                    return PageResponse.fail(err or "recall failed")
                return PageResponse.ok({"recalled": True})

            if endpoint == "/user_info" and method == "GET":
                session_key = self._get_param(request, "session_key")
                member_id = self._get_param(request, "member_id")
                return PageResponse.ok(
                    await self._user_info(plugin, session_key, member_id)
                )

            if endpoint == "/group_info" and method == "GET":
                session_key = self._get_param(request, "session_key")
                return PageResponse.ok(await self._group_info(plugin, session_key))

            if endpoint == "/label_users" and method == "GET":
                return PageResponse.ok(
                    {
                        "users": await plugin.list_labeled_users(),
                        "colors": plugin.get_label_colors(),
                        "max_per_user": plugin.get_max_labels_per_user(),
                    }
                )

            if endpoint == "/labels" and method == "GET":
                store = await plugin.labels_store()
                return PageResponse.ok(
                    {
                        "colors": plugin.get_label_colors(),
                        "max_per_user": plugin.get_max_labels_per_user(),
                        "users": [
                            {
                                "id": uid,
                                "name": record.get("name", ""),
                                "labels": list(record.get("labels", [])),
                            }
                            for uid, record in store.items()
                        ],
                    }
                )

            if endpoint == "/labels" and method == "POST":
                user_id = body.get("user_id")
                if not user_id:
                    return PageResponse.fail("user_id is required")
                ok, err = await plugin.assign_label(
                    str(user_id),
                    body.get("label") or "",
                    name=body.get("name"),
                    color=body.get("color"),
                )
                if not ok:
                    return PageResponse.fail(err or "cannot assign label")
                return PageResponse.ok(await plugin.get_user_labels(str(user_id)))

            if endpoint == "/labels" and method == "DELETE":
                user_id = body.get("user_id")
                if not user_id:
                    return PageResponse.fail("user_id is required")
                ok, err = await plugin.unassign_label(
                    str(user_id), body.get("label") or ""
                )
                if not ok:
                    return PageResponse.fail(err or "cannot remove label")
                return PageResponse.ok(await plugin.get_user_labels(str(user_id)))

            if endpoint == "/labels/rename" and method == "POST":
                user_id = body.get("user_id")
                if not user_id:
                    return PageResponse.fail("user_id is required")
                ok, err = await plugin.rename_label(
                    str(user_id),
                    body.get("label") or "",
                    body.get("new_label") or "",
                    color=body.get("color"),
                )
                if not ok:
                    return PageResponse.fail(err or "cannot rename label")
                return PageResponse.ok(await plugin.get_user_labels(str(user_id)))

            if endpoint == "/labels/delete" and method == "POST":
                removed = await plugin.delete_label_everywhere(body.get("label") or "")
                return PageResponse.ok({"removed": removed})

            if endpoint == "/image_plugin_upload" and method == "GET":
                url = plugin.image_plugin_upload_url()
                return PageResponse.ok({"enabled": bool(url), "url": url})

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

    async def _build_session_list(
        self, plugin, label_filter: set[str] | None = None
    ) -> list[dict[str, Any]]:
        store = await plugin.labels_store()
        result = []
        for key, sess in plugin.sessions.items():
            if label_filter is not None and key not in label_filter:
                continue
            takeover = sess.get("takeover", {})
            active = plugin.is_taken_over(key)
            members = sess.get("members", {}) or {}
            labels: dict[str, dict[str, Any]] = {}
            for member_id in members:
                record = store.get(str(member_id)) or {}
                for label in record.get("labels", []) or []:
                    labels.setdefault(str(label.get("name") or ""), label)
            result.append(
                {
                    "session_key": key,
                    "type": sess.get("type"),
                    "target_id": sess.get("target_id"),
                    "name": sess.get("name") or sess.get("target_id"),
                    "last_msg_at": sess.get("last_msg_at", 0),
                    "last_msg_preview": sess.get("last_msg_preview", ""),
                    "member_count": len(members),
                    "takeover_active": active,
                    "takeover_remaining": plugin.takeover_remaining(key),
                    "unread": bool(sess.get("unread")),
                    "triggered_word": sess.get("triggered_word", ""),
                    "has_labels": bool(labels),
                    "labels": list(labels.values()),
                }
            )
        # 按最后消息时间倒序
        result.sort(key=lambda x: x.get("last_msg_at", 0), reverse=True)
        return result

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
            resolved_id = str(member_id)
            name = (sess.get("members") or {}).get(resolved_id, resolved_id)
            from_group = sess.get("name")
            group_id = sess.get("target_id")
        else:
            resolved_id = str(sess.get("target_id") or "")
            name = sess.get("name")
            from_group = None
            group_id = None

        labels: list[dict[str, Any]] = []
        try:
            labels = list((await plugin.get_user_labels(resolved_id))["labels"])
        except Exception as e:  # noqa: BLE001
            logger.warning("HumanTakeover labels lookup failed: %s", e)

        # 头像/备注/用户名/来源 IM 取最近一条该用户消息(白名单字段,见 record_message)
        avatar = remark = username = source_im = None
        for entry in reversed(plugin.messages.get(session_key, [])):
            if str(entry.get("sender_id")) != resolved_id:
                continue
            avatar = entry.get("avatar") or avatar
            remark = entry.get("remark") or remark
            username = entry.get("username") or username
            source_im = entry.get("source_im") or source_im
            break

        return {
            "type": "user",
            "id": resolved_id,
            "name": name,
            "from_group": from_group,
            "group_id": group_id,
            "adapter": adapter,
            "bot_name": bot_name,
            "avatar": avatar,
            "remark": remark,
            "username": username,
            "source_im": source_im or adapter,
            "labels": labels,
        }

    async def _group_info(self, plugin, session_key: str) -> dict[str, Any]:
        """返回群聊信息卡片(含成员列表)。"""
        sess = plugin.sessions.get(session_key, {})
        store = await plugin.labels_store()
        info: dict[str, Any] = {
            "type": "group",
            "id": sess.get("target_id"),
            "name": sess.get("name"),
            "member_count": len(sess.get("members", {})),
            "members": [
                {
                    "id": str(mid),
                    "name": mname,
                    "labels": list((store.get(str(mid)) or {}).get("labels", [])),
                }
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
