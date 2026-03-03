from __future__ import annotations

import asyncio
import datetime
import json
import re
import time
from typing import Any

import httpx

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


class KeywordBitableReportListener(EventListener):
    def __init__(self):
        super().__init__()
        self._tenant_access_token: str = ""
        self._tenant_access_token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def _on_person_message(event_ctx: context.EventContext) -> None:
            await self._handle_command(event_ctx)

        @self.handler(events.GroupMessageReceived)
        async def _on_group_message(event_ctx: context.EventContext) -> None:
            await self._handle_command(event_ctx)

        # Keep compatibility with old runtimes.
        @self.handler(events.PersonNormalMessageReceived)
        async def _on_person_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_command(event_ctx)

        @self.handler(events.GroupNormalMessageReceived)
        async def _on_group_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_command(event_ctx)

    # ===== Config =====

    def _get_timeout_seconds(self) -> float:
        raw = str(self.plugin.get_config().get("timeout_seconds", "20")).strip()
        try:
            timeout = float(raw)
        except ValueError:
            timeout = 20.0
        return max(1.0, min(120.0, timeout))

    def _get_str_config(self, key: str, default: str = "") -> str:
        return str(self.plugin.get_config().get(key, default)).strip()

    def _get_bool_config(self, key: str, default: bool) -> bool:
        value = self.plugin.get_config().get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _get_int_config(self, key: str, default: int, min_value: int, max_value: int) -> int:
        raw = self.plugin.get_config().get(key, default)
        try:
            if isinstance(raw, str):
                value = int(raw.strip())
            else:
                value = int(raw)
        except Exception:
            value = default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _split_csv(raw: str) -> list[str]:
        if not raw:
            return []
        parts = re.split(r"[,\n;，；]+", raw)
        return [item.strip() for item in parts if item.strip()]

    @staticmethod
    def _dedupe_keep_order(items: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    @staticmethod
    def _normalize_command_text(text: str) -> str:
        normalized = re.sub(r"\s+", "", text.strip())
        normalized = normalized.strip("，,。.!！？?；;：:")
        return normalized

    def _resolve_commands(self) -> set[str]:
        raw = self._get_str_config("keyword_commands", "摸料")
        commands = self._split_csv(raw)
        if not commands:
            commands = ["摸料"]
        return {self._normalize_command_text(item) for item in commands if self._normalize_command_text(item)}

    # ===== Message helpers =====

    @staticmethod
    def _extract_plain_text(message_chain: platform_message.MessageChain) -> str:
        parts: list[str] = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                text = str(component.text).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _is_group_event(event_ctx: context.EventContext) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        return launcher_type == "group"

    @staticmethod
    def _is_person_event(event_ctx: context.EventContext) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        return launcher_type == "person"

    @staticmethod
    def _event_supports_reply_chain(event_ctx: context.EventContext) -> bool:
        model_fields = getattr(type(event_ctx.event), "model_fields", {})
        return isinstance(model_fields, dict) and "reply_message_chain" in model_fields

    async def _resolve_bot_uuid(self, event_ctx: context.EventContext) -> str:
        try:
            if hasattr(event_ctx, "get_bot_uuid"):
                bot_uuid = await event_ctx.get_bot_uuid()  # type: ignore[attr-defined]
                if bot_uuid:
                    return str(bot_uuid).strip()
        except Exception:
            pass
        query = getattr(event_ctx.event, "query", None)
        if query is not None:
            return str(getattr(query, "bot_uuid", "")).strip()
        return ""

    async def _send_origin_message(self, event_ctx: context.EventContext, text: str) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        if launcher_type not in {"group", "person"}:
            return False

        launcher_id = str(getattr(event_ctx.event, "launcher_id", "")).strip()
        if not launcher_id:
            return False

        bot_uuid = await self._resolve_bot_uuid(event_ctx)
        if not bot_uuid:
            return False

        await self.plugin.send_message(
            bot_uuid=bot_uuid,
            target_type=launcher_type,
            target_id=launcher_id,
            message_chain=platform_message.MessageChain([platform_message.Plain(text=text)]),
        )
        return True

    async def _reply_text(self, event_ctx: context.EventContext, text: str) -> None:
        if not text:
            return
        if self._event_supports_reply_chain(event_ctx):
            event_ctx.event.reply_message_chain = platform_message.MessageChain([platform_message.Plain(text=text)])
            return
        await self._send_origin_message(event_ctx, text)

    # ===== Feishu API =====

    async def _request_tenant_access_token(self) -> str:
        app_id = self._get_str_config("app_id", "")
        app_secret = self._get_str_config("app_secret", "")
        token_endpoint = self._get_str_config(
            "token_endpoint", "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        )
        if not app_id or not app_secret:
            raise ValueError("Plugin config app_id/app_secret is required.")

        payload = {"app_id": app_id, "app_secret": app_secret}
        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(token_endpoint, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Token endpoint failed, HTTP {response.status_code}: {response.text[:300]}")

        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("Token endpoint returned non-JSON response.") from exc

        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"Token endpoint failed, code={code}, msg={body.get('msg', '')}")

        token = str(body.get("tenant_access_token", "")).strip()
        if not token:
            raise RuntimeError("tenant_access_token is empty.")

        expire = int(body.get("expire", 7200))
        self._tenant_access_token = token
        self._tenant_access_token_expire_at = time.time() + max(60, expire - 300)
        return token

    async def _get_tenant_access_token(self) -> str:
        if self._tenant_access_token and time.time() < self._tenant_access_token_expire_at:
            return self._tenant_access_token
        async with self._token_lock:
            if self._tenant_access_token and time.time() < self._tenant_access_token_expire_at:
                return self._tenant_access_token
            return await self._request_tenant_access_token()

    async def _call_feishu_json_api(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method=method, url=endpoint, headers=headers, json=payload, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")

        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("Non-JSON response from Feishu API.") from exc

        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"code={code}, msg={body.get('msg', '')}")

        data = body.get("data", {}) or {}
        if not isinstance(data, dict):
            return {}
        return data

    async def _list_all_tables(self) -> list[dict[str, Any]]:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token:
            return []
        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables"

        page_token = ""
        tables: list[dict[str, Any]] = []
        while True:
            query: dict[str, Any] = {"page_size": 200}
            if page_token:
                query["page_token"] = page_token
            data = await self._call_feishu_json_api("GET", endpoint, headers=headers, params=query)
            items = data.get("items", []) or []
            for item in items:
                if isinstance(item, dict):
                    tables.append(item)
            if not bool(data.get("has_more", False)):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break
        return tables

    async def _resolve_sintering_table_ids(self) -> list[str]:
        explicit_ids = self._split_csv(self._get_str_config("sintering_table_ids", ""))
        if explicit_ids:
            return self._dedupe_keep_order(explicit_ids)

        target_names = self._split_csv(self._get_str_config("sintering_table_names", "A线烧结汇总,B线烧结汇总"))
        if not target_names:
            return []

        tables = await self._list_all_tables()
        name_to_id: dict[str, str] = {}
        for table in tables:
            name = str(table.get("name", "")).strip()
            table_id = str(table.get("table_id", "")).strip()
            if name and table_id:
                name_to_id[name] = table_id

        resolved: list[str] = []
        for name in target_names:
            table_id = name_to_id.get(name, "")
            if table_id:
                resolved.append(table_id)
        return self._dedupe_keep_order(resolved)

    async def _list_table_records(self, table_id: str, scan_limit: int) -> list[dict[str, Any]]:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token or not table_id:
            return []

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

        records: list[dict[str, Any]] = []
        page_token = ""
        scanned = 0
        while scanned < scan_limit:
            page_size = min(200, scan_limit - scanned)
            query: dict[str, Any] = {"page_size": page_size}
            if page_token:
                query["page_token"] = page_token
            data = await self._call_feishu_json_api("GET", endpoint, headers=headers, params=query)
            items = data.get("items", []) or []
            for item in items:
                if isinstance(item, dict):
                    records.append(item)
            scanned += len(items)
            if not bool(data.get("has_more", False)):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break
        return records

    # ===== Data extraction =====

    @staticmethod
    def _field_to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value).strip()
        return str(value).strip()

    def _is_sintering_record(self, fields: dict[str, Any], route_field: str, batch_field: str) -> bool:
        route = self._field_to_text(fields.get(route_field)).lower()
        batch = self._field_to_text(fields.get(batch_field)).upper()
        return ("sintering" in route) or ("-SC-" in batch)

    def _infer_line(self, fields: dict[str, Any], route_field: str, batch_field: str) -> str:
        route = self._field_to_text(fields.get(route_field)).lower()
        if route.endswith(".a"):
            return "A"
        if route.endswith(".b"):
            return "B"

        batch = self._field_to_text(fields.get(batch_field)).upper()
        if "-DA" in batch:
            return "A"
        if "-DB" in batch:
            return "B"
        return ""

    @staticmethod
    def _time_to_sort_key(raw: str) -> float:
        text = raw.strip()
        if not text:
            return 0.0
        try:
            value = float(text)
            if value > 1e12:
                value = value / 1000.0
            return value
        except Exception:
            pass

        iso = text.replace("Z", "+00:00")
        try:
            dt = datetime.datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
            return dt.timestamp()
        except Exception:
            pass

        fmts = ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S")
        for fmt in fmts:
            try:
                dt = datetime.datetime.strptime(text, fmt)
                dt = dt.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
                return dt.timestamp()
            except Exception:
                continue
        return 0.0

    def _build_detail_text(self, fields: dict[str, Any]) -> str:
        detail_max = self._get_int_config("detail_max_fields", 4, min_value=1, max_value=10)
        ignore_keys = {"消息时间", "原始文本", "OCR文本", "路由", "批次号", "业务类型", "产线"}

        def _value_text(v: Any) -> str:
            if isinstance(v, float):
                return f"{v:.3f}".rstrip("0").rstrip(".")
            return self._field_to_text(v)

        avg_items = [(k, v) for k, v in fields.items() if "均值" in str(k)]
        if not avg_items:
            avg_items = [(k, v) for k, v in fields.items() if ("压实" in str(k) and str(k) not in ignore_keys)]
        if not avg_items:
            avg_items = [(k, v) for k, v in fields.items() if str(k) not in ignore_keys]

        parts: list[str] = []
        for key, value in avg_items:
            k = str(key).strip()
            if not k:
                continue
            vt = _value_text(value)
            if not vt:
                continue
            parts.append(f"{k}={vt}")
            if len(parts) >= detail_max:
                break
        return ", ".join(parts)

    def _build_reply_text(
        self,
        latest_by_line: dict[str, dict[str, Any]],
        batch_field: str,
        message_time_field: str,
    ) -> str:
        no_data_text = self._get_str_config("no_data_text", "未查到出窑批次或烧结压实数据。")
        if not latest_by_line:
            return no_data_text

        lines = ["当前出窑批次及烧结压实："]
        for line_code in ("A", "B"):
            item = latest_by_line.get(line_code)
            if item is None:
                lines.append(f"{line_code}线：暂无数据")
                continue

            fields = item.get("fields", {}) or {}
            if not isinstance(fields, dict):
                lines.append(f"{line_code}线：暂无数据")
                continue

            batch_id = self._field_to_text(fields.get(batch_field))
            msg_time = self._field_to_text(fields.get(message_time_field))
            detail = self._build_detail_text(fields)

            line_text = f"{line_code}线：{batch_id or '暂无批次'}"
            if detail:
                line_text = f"{line_text} | {detail}"
            if msg_time:
                line_text = f"{line_text} | 时间 {msg_time}"
            lines.append(line_text)
        return "\n".join(lines)

    # ===== Entry =====

    async def _handle_command(self, event_ctx: context.EventContext) -> None:
        plain_text = self._extract_plain_text(event_ctx.event.message_chain)
        if not plain_text:
            return

        command = self._normalize_command_text(plain_text)
        if not command:
            return
        if command not in self._resolve_commands():
            return

        in_group = self._is_group_event(event_ctx)
        in_person = self._is_person_event(event_ctx)
        allow_group = self._get_bool_config("reply_in_group", True)
        allow_person = self._get_bool_config("reply_in_person", True)
        if (in_group and not allow_group) or (in_person and not allow_person):
            return

        event_ctx.prevent_default()
        event_ctx.prevent_postorder()

        route_field = self._get_str_config("route_field", "路由")
        batch_field = self._get_str_config("batch_field", "批次号")
        message_time_field = self._get_str_config("message_time_field", "消息时间")
        scan_limit = self._get_int_config("scan_limit", 1000, min_value=50, max_value=5000)

        try:
            table_ids = await self._resolve_sintering_table_ids()
            if not table_ids:
                await self._reply_text(event_ctx, self._get_str_config("no_data_text", "未查到出窑批次或烧结压实数据。"))
                return

            latest_by_line: dict[str, dict[str, Any]] = {}
            for table_id in table_ids:
                records = await self._list_table_records(table_id, scan_limit)
                for item in records:
                    fields = item.get("fields", {}) or {}
                    if not isinstance(fields, dict):
                        continue
                    if not self._is_sintering_record(fields, route_field, batch_field):
                        continue

                    line = self._infer_line(fields, route_field, batch_field)
                    if line not in {"A", "B"}:
                        continue

                    current_time_text = self._field_to_text(fields.get(message_time_field))
                    current_sort = self._time_to_sort_key(current_time_text)
                    existing = latest_by_line.get(line)
                    if existing is None:
                        latest_by_line[line] = {"sort": current_sort, "fields": fields}
                        continue
                    if current_sort >= float(existing.get("sort", 0.0)):
                        latest_by_line[line] = {"sort": current_sort, "fields": fields}

            reply_text = self._build_reply_text(latest_by_line, batch_field, message_time_field)
            await self._reply_text(event_ctx, reply_text)
        except Exception as exc:
            await self._reply_text(event_ctx, f"口令查询失败：{exc}")

