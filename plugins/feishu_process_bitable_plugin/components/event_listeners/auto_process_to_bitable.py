from __future__ import annotations

import asyncio
import base64
import datetime
import html
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


@dataclass
class ParsedRecord:
    scenario: str
    line: str
    batch_id: str
    route_key: str
    fields: dict[str, Any]


@dataclass
class UpsertResult:
    ok: bool
    detail: str
    record_id: str
    operation: str
    before_fields: dict[str, Any]
    after_fields: dict[str, Any]


@dataclass
class RecallHistoryEntry:
    history_record_id: str
    source_message_id: str
    target_table_id: str
    target_record_id: str
    operation: str
    before_fields: dict[str, Any]
    after_fields: dict[str, Any]
    route_key: str
    batch_id: str
    line: str
    logged_at_ts: int
    status: str


class AutoProcessToBitableListener(EventListener):
    def __init__(self):
        super().__init__()
        self._tenant_access_token: str = ""
        self._tenant_access_token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self._table_lock = asyncio.Lock()
        self._field_lock = asyncio.Lock()
        self._route_table_cache: dict[str, str] = {}
        self._route_table_override: dict[str, str] = {}
        self._table_name_to_id_cache: dict[str, str] = {}
        self._table_field_types_cache: dict[str, dict[str, int]] = {}
        self._record_lookup_cache: dict[str, str] = {}
        self._source_record_cache: dict[str, list[tuple[str, str]]] = {}
        self._history_table_id_cache: str = ""
        self._processed_event_cache: dict[str, float] = {}

    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def _on_person_message(event_ctx: context.EventContext) -> None:
            await self._handle_normal_message(event_ctx)

        @self.handler(events.GroupMessageReceived)
        async def _on_group_message(event_ctx: context.EventContext) -> None:
            await self._handle_normal_message(event_ctx)

        # Keep normal message handlers for backward compatibility with old runtimes.
        @self.handler(events.PersonNormalMessageReceived)
        async def _on_person_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_normal_message(event_ctx)

        @self.handler(events.GroupNormalMessageReceived)
        async def _on_group_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_normal_message(event_ctx)

    # ===== Common utils =====

    def _get_timeout_seconds(self) -> float:
        raw = str(self.plugin.get_config().get("timeout_seconds", "20")).strip()
        try:
            timeout = float(raw)
        except ValueError:
            timeout = 20.0
        return max(1.0, min(120.0, timeout))

    def _get_bool_config(self, key: str, default: bool) -> bool:
        value = self.plugin.get_config().get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _get_str_config(self, key: str, default: str = "") -> str:
        return str(self.plugin.get_config().get(key, default)).strip()

    def _get_int_config(
        self,
        key: str,
        default: int,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> int:
        raw = self.plugin.get_config().get(key, default)
        try:
            if isinstance(raw, str):
                value = int(raw.strip())
            else:
                value = int(raw)
        except Exception:
            value = default

        if min_value is not None:
            value = max(min_value, value)
        if max_value is not None:
            value = min(max_value, value)
        return value

    def _get_json_config(self, key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if default is None:
            default = {}
        raw = self.plugin.get_config().get(key, default)
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return default
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return default
        return default

    @staticmethod
    def _supported_production_lines() -> tuple[str, ...]:
        return ("A", "B", "C", "D", "E")

    @classmethod
    def _production_line_pattern(cls) -> str:
        return "".join(cls._supported_production_lines())

    @classmethod
    def _is_supported_production_line(cls, line: str) -> bool:
        return line.strip().upper() in cls._supported_production_lines()

    @classmethod
    def _extract_production_line_from_batch_id(cls, batch_id: str) -> str:
        match = re.search(r"(?:^|-)D([A-Z])-?\d{4}-", batch_id.strip().upper())
        if not match:
            return "UNKNOWN"
        line = str(match.group(1)).upper().strip()
        return line if cls._is_supported_production_line(line) else "UNKNOWN"

    @classmethod
    def _resolve_line_route_key(cls, prefix: str, line: str) -> str:
        line_code = line.strip().upper()
        if cls._is_supported_production_line(line_code):
            return f"{prefix}.{line_code}"
        return prefix

    def _get_time_zone(self) -> datetime.tzinfo:
        raw_tz = self._get_str_config("time_zone", "Asia/Shanghai")
        if raw_tz:
            try:
                return ZoneInfo(raw_tz)
            except Exception:
                pass
        return datetime.timezone(datetime.timedelta(hours=8))

    def _get_time_format(self) -> str:
        fmt = self._get_str_config("time_format", "%Y-%m-%d %H:%M:%S")
        if not fmt:
            return "%Y-%m-%d %H:%M:%S"
        return fmt

    @staticmethod
    def _parse_datetime_value(value: Any) -> datetime.datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=datetime.timezone.utc)
            return value

        raw = str(value).strip()
        if not raw:
            return None

        try:
            ts = float(raw)
            if ts > 1e12:
                ts = ts / 1000.0
            if ts > 0:
                return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
        except Exception:
            pass

        try:
            normalized = raw.replace("Z", "+00:00")
            parsed = datetime.datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=datetime.timezone.utc)
            return parsed
        except Exception:
            return None

    def _format_time_value(self, value: Any, *, fallback_now: bool = False) -> str:
        parsed = self._parse_datetime_value(value)
        if parsed is None:
            if fallback_now:
                parsed = datetime.datetime.now(datetime.timezone.utc)
            else:
                return str(value).strip() if value is not None else ""

        local_dt = parsed.astimezone(self._get_time_zone())
        fmt = self._get_time_format()
        try:
            return local_dt.strftime(fmt)
        except Exception:
            return local_dt.strftime("%Y-%m-%d %H:%M:%S")

    def _get_bitable_app_token(self) -> str:
        return self._get_str_config("bitable_app_token", "")

    def _get_history_table_name(self) -> str:
        table_name = self._get_str_config("history_table_name", "lb_message_history")
        if not table_name:
            return "lb_message_history"
        return table_name

    @staticmethod
    def _history_field_names() -> dict[str, str]:
        return {
            "source_message_id": "history_source_message_id",
            "target_table_id": "history_target_table_id",
            "target_record_id": "history_target_record_id",
            "operation": "history_operation",
            "before_fields_json": "history_before_fields_json",
            "after_fields_json": "history_after_fields_json",
            "route_key": "history_route_key",
            "batch_id": "history_batch_id",
            "line": "history_line",
            "logged_at_ts": "history_logged_at_ts",
            "status": "history_status",
            "note": "history_note",
        }

    async def _resolve_history_table_id(self) -> str:
        configured_table_id = self._get_str_config("history_table_id", "")
        if configured_table_id:
            self._history_table_id_cache = configured_table_id
            return configured_table_id

        if self._history_table_id_cache:
            return self._history_table_id_cache

        table_name = self._get_history_table_name()
        if not table_name:
            return ""

        cached = self._table_name_to_id_cache.get(table_name, "")
        if cached:
            self._history_table_id_cache = cached
            return cached

        async with self._table_lock:
            cached = self._table_name_to_id_cache.get(table_name, "")
            if cached:
                self._history_table_id_cache = cached
                return cached

            tables = await self._list_all_bitable_tables()
            for table in tables:
                name = str(table.get("name", "")).strip()
                tid = str(table.get("table_id", "")).strip()
                if name and tid:
                    self._table_name_to_id_cache[name] = tid

            cached = self._table_name_to_id_cache.get(table_name, "")
            if cached:
                self._history_table_id_cache = cached
                return cached

            if not self._get_bool_config("auto_create_history_table", True):
                return ""

            created = await self._create_bitable_table(table_name)
            if created:
                self._table_name_to_id_cache[table_name] = created
                self._history_table_id_cache = created
                return created

            tables = await self._list_all_bitable_tables()
            for table in tables:
                name = str(table.get("name", "")).strip()
                tid = str(table.get("table_id", "")).strip()
                if name and tid:
                    self._table_name_to_id_cache[name] = tid

            resolved = self._table_name_to_id_cache.get(table_name, "")
            if resolved:
                self._history_table_id_cache = resolved
            return resolved

    @classmethod
    def _default_table_names(cls) -> dict[str, str]:
        names = {
            "particle_size.FS": "粉碎工序粒度汇总",
            "particle_size.CM": "粗磨工序粒度汇总",
            "particle_size.XM": "细磨工序粒度汇总",
            "particle_size.HP": "合批工序粒度汇总",
            "particle_size.QQT": "喷雾工序粒度汇总",
            "particle_size": "粒度数据汇总",
            "product": "成品数据汇总",
            "product.S006": "S006成品数据汇总",
            "product.S18": "S18成品数据汇总",
            "product.S20": "S20成品数据汇总",
            "pure_water": "车间纯水PH汇总",
            "kiln_batch_io": "窑炉批次进窑出窑表",
            "kiln_batch_io.phase2": "二期窑炉批次进窑出窑表",
            "custom": "自定义消息汇总",
            "raw": "原始消息汇总",
        }

        stage_labels = {
            "spray": "喷雾",
            "feeding": "投料",
            "sintering": "烧结",
            "crushing": "粉碎压实",
            "wet_process": "湿法",
            "product": "成品",
            "pure_water": "纯水PH",
        }
        for line in cls._supported_production_lines():
            for prefix, label in stage_labels.items():
                names[f"{prefix}.{line}"] = f"{line}线{label}汇总"
        return names

    def _resolve_table_name(self, route_key: str) -> str:
        routing = self._get_json_config("table_name_routing_json", {})
        if route_key in routing and str(routing.get(route_key, "")).strip():
            return str(routing.get(route_key, "")).strip()

        prefix = route_key.split(".", 1)[0]
        if prefix in routing and str(routing.get(prefix, "")).strip():
            return str(routing.get(prefix, "")).strip()

        defaults = self._default_table_names()
        if route_key in defaults:
            return defaults[route_key]

        if "." in route_key:
            route_prefix, route_suffix = route_key.split(".", 1)
            route_suffix = route_suffix.strip().upper()
            if route_prefix == "product" and route_suffix and not self._is_supported_production_line(route_suffix):
                return f"{route_suffix}成品数据汇总"

        if prefix in defaults:
            return defaults[prefix]

        if "." in route_key:
            part_a, part_b = route_key.split(".", 1)
            if self._is_supported_production_line(part_b):
                route_labels = {
                    "spray": "喷雾",
                    "feeding": "投料",
                    "sintering": "烧结",
                    "crushing": "粉碎压实",
                    "wet_process": "湿法",
                    "product": "成品",
                    "pure_water": "纯水PH",
                }
                return f"{part_b}线{route_labels.get(part_a, part_a)}汇总"
        return f"{route_key}-汇总"

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

    async def _list_all_bitable_tables(self) -> list[dict[str, Any]]:
        app_token = self._get_bitable_app_token()
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
            has_more = bool(data.get("has_more", False))
            if not has_more:
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break

        return tables

    async def _create_bitable_table(self, table_name: str) -> str:
        app_token = self._get_bitable_app_token()
        if not app_token:
            return ""

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables"
        payload = {"table": {"name": table_name}}
        data = await self._call_feishu_json_api("POST", endpoint, headers=headers, payload=payload)

        table_id = str(data.get("table_id", "")).strip()
        if table_id:
            return table_id

        # Compatible fallback for response shapes like {"table": {"table_id": "..."}}
        table_obj = data.get("table", {}) or {}
        if isinstance(table_obj, dict):
            return str(table_obj.get("table_id", "")).strip()
        return ""

    async def _get_or_create_table_id_by_name(self, table_name: str) -> str:
        if not table_name:
            return ""

        cached = self._table_name_to_id_cache.get(table_name)
        if cached:
            return cached

        async with self._table_lock:
            cached = self._table_name_to_id_cache.get(table_name)
            if cached:
                return cached

            tables = await self._list_all_bitable_tables()
            for table in tables:
                name = str(table.get("name", "")).strip()
                tid = str(table.get("table_id", "")).strip()
                if name and tid:
                    self._table_name_to_id_cache[name] = tid

            cached = self._table_name_to_id_cache.get(table_name, "")
            if cached:
                return cached

            if not self._get_bool_config("auto_create_table_by_route", False):
                return ""

            created = await self._create_bitable_table(table_name)
            if created:
                self._table_name_to_id_cache[table_name] = created
                return created

            # Best-effort retry by re-listing once (handles concurrent creation by other workers)
            tables = await self._list_all_bitable_tables()
            for table in tables:
                name = str(table.get("name", "")).strip()
                tid = str(table.get("table_id", "")).strip()
                if name and tid:
                    self._table_name_to_id_cache[name] = tid
            return self._table_name_to_id_cache.get(table_name, "")

    async def _list_all_table_fields(self, table_id: str) -> dict[str, int]:
        app_token = self._get_bitable_app_token()
        if not app_token or not table_id:
            return {}

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"

        page_token = ""
        field_types: dict[str, int] = {}
        while True:
            query: dict[str, Any] = {"page_size": 500}
            if page_token:
                query["page_token"] = page_token
            data = await self._call_feishu_json_api("GET", endpoint, headers=headers, params=query)
            items = data.get("items", []) or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                field_name = str(item.get("field_name", "")).strip()
                raw_type = item.get("type", 0)
                if not field_name:
                    continue
                try:
                    field_types[field_name] = int(raw_type)
                except Exception:
                    field_types[field_name] = 0

            has_more = bool(data.get("has_more", False))
            if not has_more:
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break

        return field_types

    def _resolve_auto_field_type(self, value: Any) -> int:
        # Feishu Bitable field type: use text field as safe default.
        # Optionally enable numeric field auto type (2) by config.
        if self._get_bool_config("auto_numeric_field", False):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return 2
        return 1

    async def _create_table_field(self, table_id: str, field_name: str, field_type: int) -> bool:
        app_token = self._get_bitable_app_token()
        if not app_token or not table_id or not field_name:
            return False

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        payload = {
            "field_name": field_name,
            "type": field_type,
        }

        await self._call_feishu_json_api("POST", endpoint, headers=headers, payload=payload)
        return True

    async def _ensure_table_fields(self, table_id: str, write_fields: dict[str, Any]) -> tuple[bool, str, dict[str, int]]:
        if not table_id:
            return False, "table_id is empty", {}

        async with self._field_lock:
            field_types = self._table_field_types_cache.get(table_id)
            if field_types is None:
                try:
                    field_types = await self._list_all_table_fields(table_id)
                except Exception as exc:
                    return False, f"list fields failed: {exc}", {}
                self._table_field_types_cache[table_id] = field_types

            missing = [name for name in write_fields.keys() if name and name not in field_types]
            if missing and not self._get_bool_config("auto_create_fields", False):
                return False, f"missing fields: {', '.join(missing)}", field_types

            for field_name in missing:
                try:
                    field_type = self._resolve_auto_field_type(write_fields.get(field_name))
                    await self._create_table_field(table_id, field_name, field_type)
                    field_types[field_name] = field_type
                except Exception as exc:
                    return False, f"create field failed: {field_name}, {exc}", field_types

            self._table_field_types_cache[table_id] = field_types
            return True, "", field_types

    @staticmethod
    def _stringify_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value)

    def _normalize_write_fields(self, write_fields: dict[str, Any], field_types: dict[str, int]) -> dict[str, Any]:
        stringify = self._get_bool_config("stringify_text_field_values", True)
        normalized: dict[str, Any] = {}
        for key, value in write_fields.items():
            if value is None:
                continue
            ftype = field_types.get(key)
            if stringify and ftype == 1:
                normalized[key] = self._stringify_value(value)
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _strip_data_url_prefix(data: str) -> str:
        if data.startswith("data:") and "," in data:
            return data.split(",", 1)[1]
        return data

    @staticmethod
    def _truncate_text(text: str, limit: int = 5000) -> str:
        if len(text) <= limit:
            return text
        return text[:limit]

    @staticmethod
    def _normalize_dash(value: str) -> str:
        # Normalize Unicode dash/minus variants to ASCII hyphen only.
        # Avoid broad ranges that may accidentally replace non-dash characters.
        return re.sub(r"[‐‑‒–—−－]+", "-", value)

    @classmethod
    def _normalize_message_text(cls, value: str) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"(?i)</p\s*>", "\n", text)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)<[^>]+>", "", text)
        return cls._normalize_dash(text)

    @staticmethod
    def _extract_plain_text(message_chain: platform_message.MessageChain) -> str:
        parts: list[str] = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                txt = str(component.text).strip()
                if txt:
                    parts.append(txt)
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_images(message_chain: platform_message.MessageChain) -> list[platform_message.Image]:
        return [component for component in message_chain if isinstance(component, platform_message.Image)]

    def _resolve_message_time(self, event_ctx: context.EventContext) -> str:
        candidate = None
        message_event = getattr(event_ctx.event, "message_event", None)
        if message_event is not None:
            candidate = getattr(message_event, "time", None)
        if candidate in {None, ""}:
            candidate = self._extract_message_source_time(getattr(event_ctx.event, "message_chain", None))
        return self._format_time_value(candidate, fallback_now=True)

    @staticmethod
    def _is_group_event(event_ctx: context.EventContext) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        return launcher_type == "group"

    @staticmethod
    def _is_person_event(event_ctx: context.EventContext) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        return launcher_type == "person"

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

    async def _notify_private(self, event_ctx: context.EventContext, text: str) -> bool:
        target_user_id = self._get_str_config("private_notify_user_id", "")
        if not target_user_id and self._get_bool_config("private_notify_sender_when_group", False):
            target_user_id = str(getattr(event_ctx.event, "sender_id", "")).strip()
        if not target_user_id:
            return False

        bot_uuid = await self._resolve_bot_uuid(event_ctx)
        if not bot_uuid:
            return False

        try:
            await self.plugin.send_message(
                bot_uuid=bot_uuid,
                target_type="person",
                target_id=target_user_id,
                message_chain=platform_message.MessageChain([platform_message.Plain(text=text)]),
            )
            return True
        except Exception:
            return False

    async def _send_origin_message(self, event_ctx: context.EventContext, text: str) -> bool:
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        launcher_id = str(getattr(event_ctx.event, "launcher_id", "")).strip()
        if launcher_type not in {"person", "group"} or not launcher_id:
            return False

        bot_uuid = await self._resolve_bot_uuid(event_ctx)
        if not bot_uuid:
            return False

        try:
            await self.plugin.send_message(
                bot_uuid=bot_uuid,
                target_type=launcher_type,
                target_id=launcher_id,
                message_chain=platform_message.MessageChain([platform_message.Plain(text=text)]),
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _event_supports_reply_chain(event_ctx: context.EventContext) -> bool:
        model_fields = getattr(type(event_ctx.event), "model_fields", {})
        if isinstance(model_fields, dict) and "reply_message_chain" in model_fields:
            return True
        return False

    async def _send_feedback(
        self,
        event_ctx: context.EventContext,
        text: str,
        is_error: bool,
    ) -> None:
        if not text:
            return

        in_group = self._is_group_event(event_ctx)
        in_person = self._is_person_event(event_ctx)

        allow_group_reply = self._get_bool_config("reply_in_group", False)
        allow_person_reply = self._get_bool_config("reply_in_person", True)

        should_reply_origin = (in_group and allow_group_reply) or (in_person and allow_person_reply)
        if should_reply_origin:
            if self._event_supports_reply_chain(event_ctx):
                event_ctx.event.reply_message_chain = platform_message.MessageChain([platform_message.Plain(text=text)])
            else:
                await self._send_origin_message(event_ctx, text)

        if in_group:
            if is_error and self._get_bool_config("private_notify_on_error", True):
                await self._notify_private(event_ctx, text)
            if (not is_error) and self._get_bool_config("private_notify_on_write", True):
                await self._notify_private(event_ctx, text)

    @staticmethod
    def _build_record_brief(record: ParsedRecord) -> str:
        key_order = ["D10", "D50", "D90", "D99", "PH值"]
        parts: list[str] = []
        for key in key_order:
            if key in record.fields:
                parts.append(f"{key}={record.fields.get(key)}")
        if not parts:
            for key, value in record.fields.items():
                if key in {"消息时间", "原始文本", "OCR文本"}:
                    continue
                parts.append(f"{key}={value}")
                if len(parts) >= 4:
                    break

        detail = ", ".join(parts)
        if detail:
            return f"{record.route_key} | {record.batch_id} | {detail}"
        return f"{record.route_key} | {record.batch_id}"

    @staticmethod
    def _extract_message_source_time(message_chain: platform_message.MessageChain | None) -> Any:
        if message_chain is None:
            return None
        source = getattr(message_chain, "source", None)
        if source is None:
            return None
        return getattr(source, "time", None)

    @staticmethod
    def _build_message_component_signature(message_chain: platform_message.MessageChain | None) -> str:
        if message_chain is None:
            return ""

        signatures: list[str] = []
        for component in message_chain:
            if isinstance(component, platform_message.Image):
                if component.url:
                    signatures.append(f"url:{str(component.url).strip()}")
                    continue
                if component.path:
                    signatures.append(f"path:{str(component.path).strip()}")
                    continue
                if component.base64:
                    preview = AutoProcessToBitableListener._strip_data_url_prefix(str(component.base64))[:48]
                    signatures.append(f"base64:{preview}")
        return "|".join(signatures[:3])

    def _build_processed_event_key(self, event_ctx: context.EventContext) -> str:
        message_chain = getattr(event_ctx.event, "message_chain", None)
        source_message_id = self._extract_message_source_id(message_chain)
        if source_message_id:
            return f"message_id:{source_message_id}"

        source_time = self._format_time_value(self._extract_message_source_time(message_chain), fallback_now=False)
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        launcher_id = str(getattr(event_ctx.event, "launcher_id", "")).strip()
        sender_id = str(getattr(event_ctx.event, "sender_id", "")).strip()
        plain_text = ""
        if message_chain is not None:
            plain_text = re.sub(r"\s+", " ", self._extract_plain_text(message_chain)).strip()
        image_signature = self._build_message_component_signature(message_chain)
        key_parts = [launcher_type, launcher_id, sender_id, source_time, plain_text[:200], image_signature]
        normalized_parts = [part for part in key_parts if part]
        return "|".join(normalized_parts)

    def _remember_processed_event(self, processed_key: str) -> None:
        if not processed_key:
            return

        now = time.monotonic()
        self._processed_event_cache[processed_key] = now

        expire_before = now - 600.0
        stale_keys = [key for key, created_at in self._processed_event_cache.items() if created_at < expire_before]
        for stale_key in stale_keys:
            self._processed_event_cache.pop(stale_key, None)

        max_cache_size = 5000
        overflow = len(self._processed_event_cache) - max_cache_size
        if overflow > 0:
            for stale_key in list(self._processed_event_cache.keys())[:overflow]:
                self._processed_event_cache.pop(stale_key, None)

    def _mark_query_processed(self, event_ctx: context.EventContext) -> bool:
        query = getattr(event_ctx.event, "query", None)
        marker_key = "_feishu_process_bitable_processed"
        if query is not None:
            variables = getattr(query, "variables", None)
            if isinstance(variables, dict):
                if variables.get(marker_key, False):
                    return True
                variables[marker_key] = True

        processed_key = self._build_processed_event_key(event_ctx)
        if processed_key and processed_key in self._processed_event_cache:
            return True

        self._remember_processed_event(processed_key)
        return False

    @staticmethod
    def _extract_message_source_id(message_chain: platform_message.MessageChain | None) -> str:
        if message_chain is None:
            return ""
        raw = str(getattr(message_chain, "message_id", "")).strip()
        if not raw or raw == "-1":
            return ""
        return raw

    async def _safe_get_query_vars(self, event_ctx: context.EventContext) -> dict[str, Any]:
        try:
            vars_obj = await event_ctx.get_query_vars()
            if isinstance(vars_obj, dict):
                return vars_obj
        except Exception:
            pass

        query = getattr(event_ctx.event, "query", None)
        variables = getattr(query, "variables", None) if query is not None else None
        if isinstance(variables, dict):
            return variables
        return {}

    async def _extract_recall_meta(self, event_ctx: context.EventContext) -> dict[str, str] | None:
        vars_obj = await self._safe_get_query_vars(event_ctx)
        if str(vars_obj.get("_system_event", "")).strip().lower() != "message_recalled":
            return None

        recalled_message_id = str(vars_obj.get("_recalled_message_id", "")).strip()
        if not recalled_message_id:
            recalled_message_id = self._extract_message_source_id(getattr(event_ctx.event, "message_chain", None))
        if not recalled_message_id:
            return None

        return {
            "message_id": recalled_message_id,
            "chat_id": str(vars_obj.get("_recalled_chat_id", "")).strip(),
            "recall_time": str(vars_obj.get("_recalled_time", "")).strip(),
            "recall_type": str(vars_obj.get("_recalled_type", "")).strip(),
        }

    def _remember_written_record(self, source_message_id: str, table_id: str, record_id: str) -> None:
        source_id = source_message_id.strip()
        if not source_id or not table_id or not record_id:
            return

        records = self._source_record_cache.setdefault(source_id, [])
        pair = (table_id, record_id)
        if pair not in records:
            records.append(pair)

        max_source_cache = self._get_int_config("source_record_cache_size", 5000, min_value=100, max_value=20000)
        if len(self._source_record_cache) <= max_source_cache:
            return

        # Keep recently written entries only.
        overflow = len(self._source_record_cache) - max_source_cache
        for stale_key in list(self._source_record_cache.keys())[:overflow]:
            self._source_record_cache.pop(stale_key, None)

    # ===== OCR =====

    async def _get_image_bytes(self, image: platform_message.Image) -> bytes:
        if image.base64:
            try:
                normalized = self._strip_data_url_prefix(str(image.base64))
                return base64.b64decode(normalized)
            except Exception as exc:
                raise ValueError(f"Invalid image base64: {exc}") from exc

        if image.url:
            timeout = self._get_timeout_seconds()
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(str(image.url))
                if response.status_code != 200:
                    raise ValueError(f"Failed to download image from url, HTTP {response.status_code}.")
                return response.content

        if image.path:
            try:
                return Path(image.path).read_bytes()
            except Exception as exc:
                raise ValueError(f"Failed to read image from path: {exc}") from exc

        raise ValueError("Image component has no base64/url/path content.")

    async def _request_tenant_access_token(self) -> str:
        cfg = self.plugin.get_config()
        app_id = str(cfg.get("app_id", "")).strip()
        app_secret = str(cfg.get("app_secret", "")).strip()
        token_endpoint = str(
            cfg.get("token_endpoint", "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal")
        ).strip()

        if not app_id or not app_secret:
            raise ValueError("Plugin config app_id/app_secret is required.")

        timeout = self._get_timeout_seconds()
        payload = {"app_id": app_id, "app_secret": app_secret}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(token_endpoint, json=payload)

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to get tenant_access_token, HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("Token endpoint returned non-JSON response.") from exc

        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"Token endpoint failed, code={code}, msg={body.get('msg', '')}")

        token = body.get("tenant_access_token")
        if not token:
            raise RuntimeError("Token endpoint returned empty tenant_access_token.")

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

    async def _recognize_image_bytes(self, image_bytes: bytes) -> str:
        ocr_endpoint = self._get_str_config(
            "ocr_endpoint", "https://open.feishu.cn/open-apis/optical_char_recognition/v1/image/basic_recognize"
        )
        image_base64 = base64.b64encode(image_bytes).decode("ascii")
        token = await self._get_tenant_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {"image": image_base64}

        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(ocr_endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            raise RuntimeError(f"OCR request failed, HTTP {response.status_code}: {response.text[:200]}")

        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("OCR response is not JSON.") from exc

        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"OCR endpoint returned error, code={code}, msg={body.get('msg', '')}")

        data = body.get("data", {}) or {}
        text_list = data.get("text_list", []) or []
        lines: list[str] = []
        for item in text_list:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    lines.append(text.strip())
            elif isinstance(item, str) and item.strip():
                lines.append(item.strip())

        return "\n".join(lines).strip()

    # ===== Built-in parsers =====

    def _process_switch(self, key: str, default: bool = True) -> bool:
        switch = self._get_json_config(
            "process_switch_json",
            {
                "spray": True,
                "feeding": True,
                "sintering": True,
                "crushing": True,
                "particle_size": True,
                "product": True,
                "pure_water": True,
                "kiln_batch_io": True,
            },
        )
        value = switch.get(key, default)
        if isinstance(value, bool):
            return value
        return bool(value)

    def _parse_spray(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("spray", True):
            return []

        normalized_text = self._normalize_dash(text)
        line_pattern = self._production_line_pattern()
        main_regex = re.compile(
            rf"([{line_pattern}])\s*线\s*喷雾\s*批次(?:号)?\s*[:：]?\s*"
            rf"(S\d+(?:-[A-Z]{{2,3}})?-D[{line_pattern}]\d{{4}}-\d+(?:-?[A-Z]\d)?)",
            re.IGNORECASE,
        )
        params_regex = re.compile(r"([\u4e00-\u9fa5]+)\s*[:：]?\s*(\d+\.?\d*)")
        required_params = {"开度", "进口温度", "出口温度", "雾化轮转速", "水分"}

        records: list[ParsedRecord] = []
        batch_matches = list(main_regex.finditer(normalized_text))
        for idx, match in enumerate(batch_matches):
            line = str(match.group(1)).upper()
            batch_id = self._normalize_dash(str(match.group(2))).upper().strip()
            batch_id = re.sub(r"^(S\d+)-QQT-(D[AB]\d{4}-\d+(?:-?[AB]\d)?)$", r"\1-\2", batch_id, flags=re.IGNORECASE)

            block_start = match.end()
            block_end = batch_matches[idx + 1].start() if idx + 1 < len(batch_matches) else len(normalized_text)
            block_text = normalized_text[block_start:block_end]

            fields: dict[str, Any] = {}
            for key, value in params_regex.findall(block_text):
                if key in required_params:
                    try:
                        fields[key] = float(value)
                    except Exception:
                        fields[key] = value
            fields["消息时间"] = message_time
            records.append(
                ParsedRecord(
                    scenario="spray",
                    line=line,
                    batch_id=batch_id,
                    route_key=f"spray.{line}",
                    fields=fields,
                )
            )
        return records

    def _parse_qqt_moisture(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("spray", True):
            return []

        normalized_text = self._normalize_dash(text)
        line_pattern = self._production_line_pattern()
        # Example:
        # 快速水分
        # S006-QQT-DB2602-130-B-60min：1.08％MC
        moisture_regex = re.compile(
            rf"(S\d+)\s*-\s*QQT\s*-\s*D([{line_pattern}])(\d{{4}})\s*-\s*(\d+)"
            r"(?:\s*-\s*([A-Z0-9]+))?"
            r"(?:\s*-\s*(\d+)\s*MIN)?"
            r"\s*[：:]\s*(-?\d+(?:[.,]\d+)?)\s*[％%]\s*MC",
            re.IGNORECASE,
        )

        records: list[ParsedRecord] = []
        for match in moisture_regex.finditer(normalized_text):
            material_type = str(match.group(1)).upper().strip()
            line = str(match.group(2)).upper().strip()
            date_code = str(match.group(3)).strip()
            seq = str(match.group(4)).strip()
            sample_suffix = str(match.group(5) or "").upper().strip()
            hold_minutes = str(match.group(6) or "").strip()
            moisture_raw = str(match.group(7)).strip().replace(",", ".")

            try:
                moisture_value = float(moisture_raw)
            except Exception:
                continue

            batch_id = f"{material_type}-D{line}{date_code}-{seq}"
            fields: dict[str, Any] = {
                "水分": moisture_value,
                "消息时间": message_time,
            }
            if sample_suffix:
                fields["样品段"] = sample_suffix
            if hold_minutes:
                try:
                    fields["喷雾时间(min)"] = int(hold_minutes)
                except Exception:
                    fields["喷雾时间(min)"] = hold_minutes

            records.append(
                ParsedRecord(
                    scenario="spray",
                    line=line,
                    batch_id=batch_id,
                    route_key=f"spray.{line}",
                    fields=fields,
                )
            )

        return records

    def _parse_feeding(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("feeding", True):
            return []

        normalized_text = self._normalize_dash(text)
        line_pattern = self._production_line_pattern()
        batch_regex = re.compile(
            r"批次(?:号)?\s*[:：]?\s*"
            rf"(S\d+(?:-[A-Z]{{2}})?-D[{line_pattern}]\d{{4}}-\d+(?:-?[A-Z]\d)?)",
            re.IGNORECASE,
        )
        value_regexes: list[tuple[str, re.Pattern[str]]] = [
            ("磷酸铁需补(kg)", re.compile(r"磷酸铁需补\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("碳酸锂需补(kg)", re.compile(r"碳酸锂需补\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("D5总量(kg)", re.compile(r"D5(?:总量)?\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("BL总量(kg)", re.compile(r"BL(?:总量)?\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
        ]

        records: list[ParsedRecord] = []
        batch_matches = list(batch_regex.finditer(normalized_text))
        for idx, match in enumerate(batch_matches):
            batch_id = self._normalize_dash(str(match.group(1))).upper().strip()
            line = self._extract_production_line_from_batch_id(batch_id)

            block_start = match.end()
            block_end = batch_matches[idx + 1].start() if idx + 1 < len(batch_matches) else len(normalized_text)
            block_text = normalized_text[block_start:block_end]

            fields: dict[str, Any] = {}
            for field_name, pattern in value_regexes:
                value_match = pattern.search(block_text)
                if not value_match:
                    continue
                try:
                    fields[field_name] = float(value_match.group(1))
                except Exception:
                    fields[field_name] = value_match.group(1)

            if not fields:
                continue

            fields["消息时间"] = message_time
            route_key = self._resolve_line_route_key("feeding", line)
            records.append(
                ParsedRecord(
                    scenario="feeding",
                    line=line,
                    batch_id=batch_id,
                    route_key=route_key,
                    fields=fields,
                )
            )

        return records

    @staticmethod
    def _normalize_product_batch_id(raw_batch: str) -> str:
        batch = re.sub(r"\s*-\s*", "-", raw_batch.strip().upper())
        batch = re.sub(r"-{2,}", "-", batch)
        batch = re.sub(r"^(S\d+)-(D[A-E]\d{4}-\d+)", r"\1-CP-\2", batch, flags=re.IGNORECASE)
        return batch

    @staticmethod
    def _extract_product_status_fields(block_text: str) -> dict[str, Any]:
        text = re.sub(r"\s+", "", block_text.strip())
        fields: dict[str, Any] = {}
        if not text:
            return fields

        check_items: list[str] = []
        if "全检" in text:
            check_items.append("全检")
        if "水分" in text:
            check_items.append("水分")
        if "扣电" in text:
            check_items.append("扣电")
        if "三倍" in text:
            fields["检测倍率"] = "三倍"

        if check_items:
            fields["送检项目"] = "、".join(dict.fromkeys(check_items))
        if "已送检" in text or "已送" in text:
            fields["送检状态"] = "已送检"

        attention_items: list[str] = []
        for label in ("铜锌颗粒", "大颗粒"):
            if label in text:
                attention_items.append(label)
        if attention_items:
            fields["关注项"] = "、".join(attention_items)

        feeding_match = re.search(r"([A-E][12])下(?:的)?料", text, flags=re.IGNORECASE)
        if feeding_match:
            fields["下料段位"] = feeding_match.group(1).upper()
        package_matches = re.findall(r"([A-E][12])下(\d+)包", text, flags=re.IGNORECASE)
        if package_matches:
            fields["下料说明"] = "；".join(f"{slot.upper()}下{count}包" for slot, count in package_matches)

        return fields

    @classmethod
    def _extract_product_metric_fields(cls, block_text: str) -> dict[str, Any]:
        text = cls._normalize_message_text(block_text)
        compact = re.sub(r"\s+", "", text)
        fields: dict[str, Any] = {}

        metric_aliases: list[tuple[str, tuple[str, ...]]] = [
            ("成品压实", ("成品压实", "压实密度", "压实")),
            ("0.1C充电", ("0.1C充电", "0.1C充", "0.1C充容", "0.1C充电容量")),
            ("0.1C放电", ("0.1C放电", "0.1C放", "0.1C放容", "0.1C放电容量")),
            ("首效", ("0.1C首效", "首效", "首次效率")),
            ("平台效率", ("3.2V容量占比", "3.2V平台效率", "2.95V容量占比", "平台效率")),
            ("残碱(Li+)", ("残碱(Li+)", "Li+含量", "Li含量", "Li+", "残碱锂", "残锂")),
            ("碳含量", ("碳含量", "C含量")),
            ("粉阻(粉末电阻)", ("粉阻(粉末电阻)", "粉末电阻", "粉阻")),
            ("比表(麦克比表)", ("比表(麦克比表)", "麦克比表", "比表面积", "比表")),
            ("pH", ("pH", "PH", "Hp")),
        ]
        all_aliases = [alias for _field_name, aliases in metric_aliases for alias in aliases]

        def _normalize_metric_value(field_name: str, value: float) -> float:
            if field_name == "首效" and value > 1000:
                return value / 100.0
            return value

        def _extract_alias_value(alias: str) -> float | None:
            pattern = rf"{re.escape(alias)}(?:值|均值|结果)?\s*[:：=]?\s*(?<![\dA-Za-z])(-?\d+(?:\.\d+)?)(?![\dA-Za-z.])"
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except Exception:
                    return None

            compact_alias = re.sub(r"\s+", "", alias)
            start = compact.lower().find(compact_alias.lower())
            if start < 0:
                return None
            segment_start = start + len(compact_alias)
            segment_end = len(compact)
            for other_alias in all_aliases:
                compact_other = re.sub(r"\s+", "", other_alias)
                if not compact_other or compact_other.lower() == compact_alias.lower():
                    continue
                other_pos = compact.lower().find(compact_other.lower(), segment_start)
                if other_pos >= 0:
                    segment_end = min(segment_end, other_pos)
            segment = compact[segment_start:segment_end]
            if re.search(r"S\d+.*D[A-Z]\d{4}", segment, flags=re.IGNORECASE):
                return None
            match = re.search(
                r"(?:值|均值|结果)?[:：=]?(?<![\dA-Za-z])(-?\d+(?:\.\d+)?)(?![\dA-Za-z.])",
                segment,
                flags=re.IGNORECASE,
            )
            if not match:
                return None
            try:
                return float(match.group(1))
            except Exception:
                return None

        def _match_metric_field(cell_text: str) -> str | None:
            compact_cell = re.sub(r"\s+", "", cell_text).lower()
            if not compact_cell:
                return None
            for field_name, aliases in metric_aliases:
                for alias in aliases:
                    compact_alias = re.sub(r"\s+", "", alias).lower()
                    if compact_alias and compact_alias in compact_cell:
                        return field_name
            return None

        def _numeric_cell_value(cell_text: str) -> float | None:
            stripped = cell_text.strip()
            if re.fullmatch(r"\d{4}[./-]\d{1,2}[./-]\d{1,2}", stripped):
                return None
            if re.search(r"S\d+.*D[A-Z]\d{4}", stripped, flags=re.IGNORECASE):
                return None
            match = re.fullmatch(r"-?\d+(?:\.\d+)?%?", stripped)
            if not match:
                return None
            try:
                return float(stripped.rstrip("%"))
            except Exception:
                return None

        def _extract_table_values_by_header_order() -> dict[str, float]:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            header_positions: list[tuple[int, str]] = []
            seen_fields: set[str] = set()
            for idx, line in enumerate(lines):
                field_name = _match_metric_field(line)
                if not field_name or field_name in seen_fields:
                    continue
                header_positions.append((idx, field_name))
                seen_fields.add(field_name)
            if not header_positions:
                return {}

            first_value_idx = header_positions[-1][0] + 1
            numeric_values: list[float] = []
            for line in lines[first_value_idx:]:
                value = _numeric_cell_value(line)
                if value is not None:
                    numeric_values.append(value)
            if not numeric_values:
                return {}

            table_fields: dict[str, float] = {}
            for (_idx, field_name), value in zip(header_positions, numeric_values):
                table_fields[field_name] = _normalize_metric_value(field_name, value)
            return table_fields

        for field_name, aliases in metric_aliases:
            for alias in aliases:
                value = _extract_alias_value(alias)
                if value is None:
                    continue
                fields[field_name] = _normalize_metric_value(field_name, value)
                break

        for field_name, value in _extract_table_values_by_header_order().items():
            fields.setdefault(field_name, value)

        return fields

    @staticmethod
    def _extract_product_date_field(block_text: str) -> dict[str, Any]:
        match = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", block_text)
        if not match:
            return {}
        year, month, day = match.groups()
        return {"检测日期": f"{int(year):04d}.{int(month):02d}.{int(day):02d}"}

    def _parse_product(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("product", True):
            return []

        normalized_text = self._normalize_message_text(text)
        line_pattern = self._production_line_pattern()
        batch_regex = re.compile(
            rf"(S\d+)\s*(?:-\s*CP)?\s*-+\s*D([{line_pattern}])\s*(\d{{4}})\s*-\s*(\d+)"
            rf"(?:\s*-\s*([A-Z]{{1,4}})\s*-\s*([{line_pattern}][12])|\s*-\s*([{line_pattern}][12])|\s*-\s*([A-Z]{{1,4}})(?!\d))?",
            re.IGNORECASE,
        )
        matches = list(batch_regex.finditer(normalized_text))
        if not matches:
            return []

        records: list[ParsedRecord] = []
        for idx, match in enumerate(matches):
            material_type = str(match.group(1)).upper().strip()
            line = str(match.group(2)).upper().strip()
            date_code = str(match.group(3)).strip()
            seq = str(match.group(4)).strip()
            suffix = str(match.group(5) or "").upper().strip()
            segment = str(match.group(6) or match.group(7) or "").upper().strip()
            suffix_only = str(match.group(8) or "").upper().strip()
            if not suffix and suffix_only:
                suffix = suffix_only
            if not self._is_supported_production_line(line):
                continue

            sample_batch_id = f"{material_type}-D{line}{date_code}-{seq}"
            if suffix:
                sample_batch_id = f"{sample_batch_id}-{suffix}"
            if segment:
                sample_batch_id = f"{sample_batch_id}-{segment}"

            batch_id = f"{material_type}-CP-D{line}{date_code}-{seq}"
            if segment:
                batch_id = f"{batch_id}-{segment}"
            elif suffix:
                batch_id = f"{batch_id}-{suffix}"
            start_pos = match.end()
            end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized_text)
            block_text = normalized_text[start_pos:end_pos]
            if len(matches) == 1:
                block_text = normalized_text

            fields: dict[str, Any] = {
                "物料类型": material_type,
                "成品批次": batch_id,
                "样品批号": sample_batch_id,
                "产线": line,
                "段位": segment,
                "消息时间": message_time,
            }
            if suffix:
                fields["成品后缀"] = suffix
            fields.update(self._extract_product_status_fields(block_text))
            fields.update(self._extract_product_metric_fields(block_text))
            fields.update(self._extract_product_date_field(block_text))

            records.append(
                ParsedRecord(
                    scenario="product",
                    line=line,
                    batch_id=batch_id,
                    route_key=f"product.{material_type}",
                    fields=fields,
                )
            )

        return records

    def _parse_sintering(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("sintering", True):
            return []

        normalized_text = self._normalize_dash(text)
        line_pattern = self._production_line_pattern()
        regex = re.compile(
            rf"(S\d+-SC-[A-Z]{{2}}\d{{4}}-\d+)-([{line_pattern}]\d+-\d+)-\d+\s*min\s*[:：]\s*([\d\.]+)",
            re.IGNORECASE,
        )

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for match in regex.finditer(normalized_text):
            base_id, sample_id, value = match.groups()
            base_id = base_id.upper().strip()
            sample_id = sample_id.upper().strip()
            line = sample_id[:1]
            if not self._is_supported_production_line(line):
                continue

            key = (base_id, line)
            if key not in grouped:
                grouped[key] = {"消息时间": message_time}

            grouped[key][sample_id] = float(value)

        records: list[ParsedRecord] = []
        for (batch_id, line), fields in grouped.items():
            average_map: dict[str, list[float]] = {}
            for sample_id, value in list(fields.items()):
                if sample_id == "消息时间":
                    continue
                if not isinstance(value, (int, float)):
                    continue
                prefix = sample_id.split("-")[0]
                average_map.setdefault(prefix, []).append(float(value))

            for prefix, values in average_map.items():
                if values:
                    fields[f"{prefix}-均值"] = round(sum(values) / len(values), 3)

            records.append(
                ParsedRecord(
                    scenario="sintering",
                    line=line,
                    batch_id=batch_id,
                    route_key=self._resolve_line_route_key("sintering", line),
                    fields=fields,
                )
            )

        return records

    def _split_sample_id(self, sample_id: str) -> tuple[str, str | None]:
        sample_id = sample_id.strip()
        freq_match = re.search(r"(?i)(?:-|\s*)(\d+(?:\.\d+)?)\s*HZ[\s\)\]）】]*$", sample_id)
        if freq_match:
            base = sample_id[: freq_match.start()].rstrip().rstrip("-").rstrip()
            if base:
                return base, f"{freq_match.group(1).upper()}HZ"

        parts = sample_id.split("-")
        if len(parts) >= 2 and re.fullmatch(r"\d+(?:\.\d+)?HZ", parts[-1].strip(), re.IGNORECASE):
            return "-".join(parts[:-1]), parts[-1].upper().strip()

        return sample_id, None

    @staticmethod
    def _normalize_hyphen_token(value: str) -> str:
        return re.sub(r"\s*-\s*", "-", value.strip())

    @staticmethod
    def _resolve_fs_slot(sample_text: str) -> str:
        text = sample_text.strip().upper()
        match = re.search(r"\b([A-E][12])\b", text)
        if not match:
            return ""
        return str(match.group(1))

    @classmethod
    def _resolve_fs_subline(cls, sample_text: str) -> str:
        slot = cls._resolve_fs_slot(sample_text)
        if slot.endswith("1"):
            return "1线"
        if slot.endswith("2"):
            return "2线"
        return ""

    @staticmethod
    def _extract_minutes_from_sample(sample_text: str) -> int | None:
        match = re.search(r"(?i)(\d+)\s*MIN", sample_text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None

    @staticmethod
    def _extract_number(value: str) -> float | None:
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if not match:
            return None
        try:
            return float(match.group(0))
        except Exception:
            return None

    @staticmethod
    def _normalize_crushing_batch_id(batch_id: str) -> str:
        normalized = re.sub(r"\s*-\s*", "-", batch_id.strip()).upper()
        if re.fullmatch(r"S\d+-D[A-E]\d{4}-\d+", normalized, re.IGNORECASE):
            return re.sub(r"^(S\d+)-", r"\1-FS-", normalized, flags=re.IGNORECASE)
        return normalized

    def _parse_crushing(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("crushing", True):
            return []

        normalized_text = self._normalize_dash(text)
        regex = re.compile(
            r"(S\d+\s*-\s*FS\s*-\s*[A-Z]{2}\d{4}\s*-\s*\d+)\s*-\s*([A-E][12][^：:\n]*)[：:]\s*(-?\d+(?:\.\d+)?)",
            re.IGNORECASE,
        )

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for match in regex.finditer(normalized_text):
            base_id, sample_id, value = match.groups()
            base_id = self._normalize_crushing_batch_id(base_id)
            sample_id = self._normalize_hyphen_token(sample_id).upper().strip()
            sample_key, freq = self._split_sample_id(sample_id)

            line = self._extract_production_line_from_batch_id(base_id)
            if line == "UNKNOWN":
                sample_line = sample_key[:1]
                line = sample_line if self._is_supported_production_line(sample_line) else "UNKNOWN"

            if not self._is_supported_production_line(line):
                continue

            key = (base_id, line)
            if key not in grouped:
                grouped[key] = {"消息时间": message_time}

            grouped[key][sample_key] = float(value)
            if freq:
                grouped[key][f"{sample_key}_频率"] = freq

            fs_subline = self._resolve_fs_subline(sample_key)
            fs_slot = self._resolve_fs_slot(sample_key)
            if fs_subline:
                prefix = f"粉碎{fs_subline}"
                grouped[key][f"{prefix}线别"] = fs_subline
            else:
                prefix = "粉碎"
            if fs_slot:
                grouped[key][f"{prefix}机位"] = fs_slot
            grouped[key][f"{prefix}压实值"] = float(value)
            hold_minutes = self._extract_minutes_from_sample(sample_key)
            if hold_minutes is not None:
                grouped[key][f"{prefix}粉碎时间（min）"] = hold_minutes
            if freq:
                freq_value = self._extract_number(freq)
                grouped[key][f"{prefix}频率(HZ)"] = freq_value if freq_value is not None else freq

        operation_head_regex = re.compile(
            r"([A-E][12])\s*粉碎\s*[:：]\s*(S\d+\s*-\s*D[A-E]\d{4}\s*-\s*\d+)",
            re.IGNORECASE,
        )
        operation_matches = list(operation_head_regex.finditer(normalized_text))
        operation_param_rules: list[tuple[str, re.Pattern[str]]] = [
            ("分级电机(HZ)", re.compile(r"分级电机\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*HZ", re.IGNORECASE)),
            ("喂料频率(HZ)", re.compile(r"喂料频率\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*HZ", re.IGNORECASE)),
            ("研磨压力(KPa)", re.compile(r"研磨压力\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*KPA", re.IGNORECASE)),
            ("密封气压(Pa)", re.compile(r"密封气压\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*PA", re.IGNORECASE)),
            ("收尘差压(KPa)", re.compile(r"收尘差压\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*KPA", re.IGNORECASE)),
            ("过滤器压(Pa)", re.compile(r"过滤器压\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*PA", re.IGNORECASE)),
            ("露点(°C)", re.compile(r"露点\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*°?\s*C", re.IGNORECASE)),
        ]

        for idx, match in enumerate(operation_matches):
            fs_slot = str(match.group(1)).upper().strip()
            batch_id_raw = str(match.group(2))
            batch_id = self._normalize_crushing_batch_id(batch_id_raw)

            line = self._extract_production_line_from_batch_id(batch_id)
            if line == "UNKNOWN":
                slot_line = fs_slot[:1]
                line = slot_line if self._is_supported_production_line(slot_line) else "UNKNOWN"
            if not self._is_supported_production_line(line):
                continue

            start_pos = match.end()
            end_pos = operation_matches[idx + 1].start() if idx + 1 < len(operation_matches) else len(normalized_text)
            block_text = normalized_text[start_pos:end_pos]

            key = (batch_id, line)
            if key not in grouped:
                grouped[key] = {"消息时间": message_time}

            fs_subline = self._resolve_fs_subline(fs_slot)
            prefix = f"粉碎{fs_subline}" if fs_subline else "粉碎"
            if fs_subline:
                grouped[key][f"{prefix}线别"] = fs_subline
            grouped[key][f"{prefix}机位"] = fs_slot

            for field_name, pattern in operation_param_rules:
                param_match = pattern.search(block_text)
                if not param_match:
                    continue
                try:
                    grouped[key][f"{prefix}{field_name}"] = float(param_match.group(1))
                except Exception:
                    grouped[key][f"{prefix}{field_name}"] = str(param_match.group(1)).strip()

        records: list[ParsedRecord] = []
        for (batch_id, line), fields in grouped.items():
            records.append(
                ParsedRecord(
                    scenario="crushing",
                    line=line,
                    batch_id=batch_id,
                    route_key=self._resolve_line_route_key("crushing", line),
                    fields=fields,
                )
            )

        return records

    def _parse_pure_water(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("pure_water", True):
            return []

        normalized_text = self._normalize_dash(text)
        line_pattern = self._production_line_pattern()
        ph_match = re.search(
            rf"车间\s*(?:[{line_pattern}](?:\s*[/／、&]\s*[{line_pattern}])*|[{line_pattern}]+)?\s*线?\s*纯水\s*PH(?:值)?\s*[:：]\s*(\d+\.?\d*)",
            normalized_text,
            re.IGNORECASE,
        )
        if not ph_match:
            return []

        batch_regex = re.compile(r"(S\d+-TL-D[A-E]\d{4}-\d+)", re.IGNORECASE)
        batch_matches = [self._normalize_dash(m.group(1)).upper().strip() for m in batch_regex.finditer(normalized_text)]
        if not batch_matches:
            return []

        batch_id = "\n".join(batch_matches)
        ph_value = float(ph_match.group(1))

        batch_lines = {self._extract_production_line_from_batch_id(bid) for bid in batch_matches}
        batch_lines.discard("UNKNOWN")
        if len(batch_lines) == 1:
            line = next(iter(batch_lines))
        else:
            line = "MIXED"

        route_key = self._resolve_line_route_key("pure_water", line)
        fields = {
            "PH值": ph_value,
            "消息时间": message_time,
        }
        return [
            ParsedRecord(
                scenario="pure_water",
                line=line,
                batch_id=batch_id,
                route_key=route_key,
                fields=fields,
            )
        ]

    @staticmethod
    def _preferred_kiln_segments() -> set[str]:
        return {"A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2"}

    @classmethod
    def _normalize_kiln_segment(cls, segment_text: str) -> str:
        segment = segment_text.strip().upper()
        if not segment:
            return ""
        if segment in cls._preferred_kiln_segments():
            return segment
        if re.fullmatch(r"[A-Z]{1,4}\d?", segment):
            return segment
        return ""

    def _resolve_kiln_message_datetime(self, message_time: str) -> datetime.datetime:
        raw_message_time = str(message_time).strip()
        time_zone = self._get_time_zone()
        time_format = self._get_time_format()
        if raw_message_time and time_format:
            try:
                parsed = datetime.datetime.strptime(raw_message_time, time_format)
                return parsed.replace(tzinfo=time_zone)
            except Exception:
                pass

        datetime_match = re.search(
            r"(\d{4})-(\d{2})-(\d{2})(?:\D+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
            raw_message_time,
        )
        if datetime_match:
            try:
                return datetime.datetime(
                    year=int(datetime_match.group(1)),
                    month=int(datetime_match.group(2)),
                    day=int(datetime_match.group(3)),
                    hour=int(datetime_match.group(4) or 0),
                    minute=int(datetime_match.group(5) or 0),
                    second=int(datetime_match.group(6) or 0),
                    tzinfo=time_zone,
                )
            except Exception:
                pass

        return datetime.datetime.now(time_zone)

    def _resolve_kiln_message_date(self, message_time: str) -> datetime.date:
        return self._resolve_kiln_message_datetime(message_time).date()

    def _compose_kiln_event_time(self, message_time: str, hour: int, minute: int) -> str:
        message_dt = self._resolve_kiln_message_datetime(message_time)
        event_dt = datetime.datetime(
            year=message_dt.year,
            month=message_dt.month,
            day=message_dt.day,
            hour=hour,
            minute=minute,
            second=0,
            tzinfo=self._get_time_zone(),
        )

        # Kiln messages only carry HH:mm, so correct obvious midnight crossings
        # without changing normal same-day records.
        cross_day_threshold = datetime.timedelta(hours=18)
        delta = event_dt - message_dt
        if delta >= cross_day_threshold:
            event_dt -= datetime.timedelta(days=1)
        elif delta <= -cross_day_threshold:
            event_dt += datetime.timedelta(days=1)

        time_format = self._get_time_format()
        try:
            return event_dt.strftime(time_format)
        except Exception:
            return event_dt.strftime("%Y-%m-%d %H:%M:%S")

    def _get_kiln_batch_io_row_mode(self) -> str:
        row_mode = self._get_str_config("kiln_batch_io_row_mode", "segment").lower()
        if row_mode in {"segment", "slot"}:
            return row_mode
        return "segment"

    @staticmethod
    def _resolve_kiln_batch_io_route_key(line: str) -> str:
        return "kiln_batch_io.phase2" if line.strip().upper() in {"C", "D", "E"} else "kiln_batch_io"

    def _parse_kiln_batch_io(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("kiln_batch_io", True):
            return []

        normalized_text = self._normalize_dash(text)
        inline_event_regex = re.compile(
            r"(?m)^\s*(D[A-E]-?\d{4}-\d+)\s*"
            r"(开始\s*进窑|结束\s*进窑|进窑\s*开始|进窑\s*结束|"
            r"开始\s*出窑|结束\s*出窑|出窑\s*开始|出窑\s*结束|"
            r"进窑|出窑|开始|结束)\s*(?:时间)?\s*"
            r"(\d{1,2})\s*[：:]\s*(\d{2})\s*$",
            re.IGNORECASE,
        )
        batch_header_regex = re.compile(
            r"([A-Z0-9]+(?:-[A-Z0-9]+)*)\s*批次\s*(开始|结束)\s*(进窑|出窑)",
            re.IGNORECASE,
        )
        detail_line_regex = re.compile(
            r"(?m)^\s*([A-Z]{1,4}\d?)\s*-+\s*(\d+)\s*-+\s*(\d{1,2})\s*[：:]\s*(\d{2})\s*$",
            re.IGNORECASE,
        )
        action_to_field: dict[tuple[str, str], str] = {
            ("进窑", "开始"): "进窑开始时间",
            ("进窑", "结束"): "进窑结束时间",
            ("出窑", "开始"): "出窑开始时间",
            ("出窑", "结束"): "出窑结束时间",
        }
        row_mode = self._get_kiln_batch_io_row_mode()

        records: list[ParsedRecord] = []
        for inline_match in inline_event_regex.finditer(normalized_text):
            batch_id = re.sub(
                r"^D([A-E])-(\d{4}-\d+)$",
                r"D\1\2",
                str(inline_match.group(1)).upper().strip(),
            )
            action_text = re.sub(r"\s+", "", str(inline_match.group(2)).strip())
            if "进窑" in action_text:
                time_field = "进窑结束时间" if "结束" in action_text else "进窑开始时间"
            elif "出窑" in action_text:
                time_field = "出窑结束时间" if "结束" in action_text else "出窑开始时间"
            elif "结束" in action_text:
                time_field = "进窑结束时间"
            else:
                time_field = "进窑开始时间"

            try:
                hour = int(str(inline_match.group(3)).strip())
                minute = int(str(inline_match.group(4)).strip())
            except Exception:
                continue
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                continue

            line = self._extract_production_line_from_batch_id(batch_id)
            records.append(
                ParsedRecord(
                    scenario="kiln_batch_io",
                    line=line,
                    batch_id=batch_id,
                    route_key=self._resolve_kiln_batch_io_route_key(line),
                    fields={
                        time_field: self._compose_kiln_event_time(message_time, hour, minute),
                        "消息时间": message_time,
                    },
                )
            )

        batch_headers = list(batch_header_regex.finditer(normalized_text))
        for idx, header_match in enumerate(batch_headers):
            batch_id = self._normalize_dash(str(header_match.group(1))).upper().strip()
            stage_status = str(header_match.group(2)).strip()
            stage_action = str(header_match.group(3)).strip()
            time_field = action_to_field.get((stage_action, stage_status), "")
            if not batch_id or not time_field:
                continue
            route_key = self._resolve_kiln_batch_io_route_key(
                self._extract_production_line_from_batch_id(batch_id)
            )

            block_start = header_match.end()
            block_end = batch_headers[idx + 1].start() if idx + 1 < len(batch_headers) else len(normalized_text)
            block_text = normalized_text[block_start:block_end]

            for detail_match in detail_line_regex.finditer(block_text):
                segment = self._normalize_kiln_segment(str(detail_match.group(1)))
                if not segment:
                    continue

                position = str(detail_match.group(2)).strip()
                try:
                    hour = int(str(detail_match.group(3)).strip())
                    minute = int(str(detail_match.group(4)).strip())
                except Exception:
                    continue
                if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                    continue

                event_time = self._compose_kiln_event_time(message_time, hour, minute)
                if row_mode == "slot":
                    line = f"{segment}-{position}"
                    fields: dict[str, Any] = {
                        "窑炉段": segment,
                        "窑位": position,
                        time_field: event_time,
                        "消息时间": message_time,
                    }
                else:
                    line = segment
                    position_time_field = f"{position}号{time_field}"
                    fields = {
                        "窑炉段": segment,
                        position_time_field: event_time,
                        "消息时间": message_time,
                    }
                records.append(
                    ParsedRecord(
                        scenario="kiln_batch_io",
                        line=line,
                        batch_id=batch_id,
                        route_key=route_key,
                        fields=fields,
                    )
                )

        return records

    @staticmethod
    def _particle_process_name_map() -> dict[str, str]:
        return {
            "FS": "粉碎工序",
            "CM": "粗磨工序",
            "XM": "细磨工序",
            "HP": "合批工序",
            "SC": "烧结工序",
            "QQT": "喷雾工序",
        }

    @staticmethod
    def _wet_process_field_prefix_map() -> dict[str, str]:
        return {
            "CM": "粗磨",
            "XM": "细磨",
            "HP": "合批",
        }

    @staticmethod
    def _resolve_xm_sample_slot(sample_suffix: str) -> str:
        suffix = sample_suffix.strip().upper()
        match = re.search(r"[ABCD]", suffix)
        if not match:
            return ""
        return str(match.group(0))

    @classmethod
    def _resolve_xm_subline(cls, sample_suffix: str) -> str:
        slot = cls._resolve_xm_sample_slot(sample_suffix)
        if slot in {"A", "B"}:
            return "1线"
        if slot in {"C", "D"}:
            return "2线"
        return ""

    @staticmethod
    def _normalize_sample_suffix_and_hold_minutes(sample_suffix: str, hold_minutes: str) -> tuple[str, str]:
        normalized_suffix = sample_suffix.strip().upper()
        normalized_minutes = hold_minutes.strip()

        if normalized_suffix and not normalized_minutes:
            minute_match = re.fullmatch(r"(\d+)\s*MIN", normalized_suffix, re.IGNORECASE)
            if minute_match:
                normalized_suffix = ""
                normalized_minutes = str(minute_match.group(1)).strip()

        return normalized_suffix, normalized_minutes

    def _resolve_particle_route_key(self, process_code: str, line: str) -> str:
        code = process_code.strip().upper()
        line_code = line.strip().upper()

        if not self._get_bool_config("merge_particle_size_to_stage_tables", True):
            return f"particle_size.{code}"

        if code == "FS":
            return self._resolve_line_route_key("crushing", line_code)
        if code in {"CM", "XM", "HP"}:
            return self._resolve_line_route_key("wet_process", line_code)
        if code == "SC":
            return self._resolve_line_route_key("sintering", line_code)
        if code == "QQT":
            return self._resolve_line_route_key("spray", line_code)
        return f"particle_size.{code}"

    @staticmethod
    def _extract_particle_d_values(text: str) -> dict[str, float]:
        values: dict[str, float] = {}
        for label in ("10", "50", "90", "99"):
            patterns = [
                re.compile(rf"(?i)\bD\s*{label}\b\s*[:：=]?\s*(-?\d+(?:[.,]\d+)?)"),
                re.compile(rf"(?i)\bD\s*V\s*[\(\[]?\s*{label}\s*[\)\]]?\s*[:：=]?\s*(-?\d+(?:[.,]\d+)?)"),
            ]

            match = None
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    break
            if not match:
                continue
            raw = str(match.group(1)).strip().replace(",", ".")
            try:
                values[f"D{label}"] = float(raw)
            except Exception:
                continue
        return values

    def _parse_particle_size(
        self,
        text: str,
        message_time: str,
        *,
        allow_empty_d_values: bool = False,
    ) -> list[ParsedRecord]:
        if not self._process_switch("particle_size", True):
            return []

        normalized_text = self._normalize_dash(text)
        process_name_map = self._particle_process_name_map()
        wet_prefix_map = self._wet_process_field_prefix_map()
        # Support formats like:
        # S18-XM-DA2603-002
        # S18-XM-DA2603-002-C
        # S18-XM-DA2603-002-C-120min
        line_pattern = self._production_line_pattern()
        batch_regex = re.compile(
            rf"(S\d+)\s*-\s*([A-Z]{{2,3}})\s*-\s*D([{line_pattern}])(\d{{4}})\s*-\s*(\d+)"
            r"(?:\s*-\s*([A-Z0-9]+))?"
            r"(?:\s*-\s*(\d+)\s*MIN)?",
            re.IGNORECASE,
        )

        matches = list(batch_regex.finditer(normalized_text))
        if not matches:
            return []

        whole_d_values = self._extract_particle_d_values(normalized_text)
        xm_suffix_hints: dict[tuple[str, str, str, str, str], tuple[str, str]] = {}
        records: list[ParsedRecord] = []

        for idx, match in enumerate(matches):
            material_type = str(match.group(1)).upper().strip()
            process_code = str(match.group(2)).upper().strip()
            line = str(match.group(3)).upper().strip()
            date_code = str(match.group(4)).strip()
            seq = str(match.group(5)).strip()
            sample_suffix = str(match.group(6) or "").upper().strip()
            hold_minutes = str(match.group(7) or "").strip()
            sample_suffix, hold_minutes = self._normalize_sample_suffix_and_hold_minutes(sample_suffix, hold_minutes)

            batch_meta_key = (material_type, process_code, line, date_code, seq)
            if process_code == "XM":
                if sample_suffix:
                    hinted_hold = hold_minutes
                    if not hinted_hold and batch_meta_key in xm_suffix_hints:
                        hinted_hold = xm_suffix_hints[batch_meta_key][1]
                    xm_suffix_hints[batch_meta_key] = (sample_suffix, hinted_hold)
                elif batch_meta_key in xm_suffix_hints:
                    hinted_suffix, hinted_hold = xm_suffix_hints[batch_meta_key]
                    sample_suffix = hinted_suffix
                    if not hold_minutes and hinted_hold:
                        hold_minutes = hinted_hold

            if process_code not in process_name_map:
                continue

            route_key = self._resolve_particle_route_key(process_code, line)
            if route_key.startswith("wet_process."):
                # Wet-process summary table requires one row per production batch.
                batch_id = f"{material_type}-D{line}{date_code}-{seq}"
            elif route_key.startswith("spray.") and process_code == "QQT":
                # Align QQT particle-size with spray process batch id for upsert merge.
                batch_id = f"{material_type}-D{line}{date_code}-{seq}"
            else:
                batch_id = f"{material_type}-{process_code}-D{line}{date_code}-{seq}"

            start_pos = match.start()
            end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized_text)
            block_text = normalized_text[start_pos:end_pos]
            d_values = self._extract_particle_d_values(block_text)
            if not d_values and len(matches) == 1:
                d_values = dict(whole_d_values)
            if not d_values and not allow_empty_d_values:
                continue

            fields: dict[str, Any] = {
                "物料类型": material_type,
                "消息时间": message_time,
            }

            if route_key.startswith("wet_process.") and process_code in wet_prefix_map:
                prefix = wet_prefix_map[process_code]
                fields["最后更新工序"] = process_name_map[process_code]

                dynamic_prefix = prefix
                if process_code == "XM" and sample_suffix:
                    xm_subline = self._resolve_xm_subline(sample_suffix)
                    xm_slot = self._resolve_xm_sample_slot(sample_suffix)
                    if xm_subline:
                        dynamic_prefix = f"{prefix}{xm_subline}"
                        fields[f"{dynamic_prefix}线别"] = xm_subline
                    if xm_slot:
                        fields[f"{dynamic_prefix}段位"] = xm_slot
                    fields[f"{dynamic_prefix}样品段"] = sample_suffix
                elif sample_suffix:
                    fields[f"{dynamic_prefix}样品段"] = sample_suffix

                if hold_minutes:
                    try:
                        fields[f"{dynamic_prefix}研磨时间(min)"] = int(hold_minutes)
                    except Exception:
                        fields[f"{dynamic_prefix}研磨时间(min)"] = hold_minutes

                for d_key, d_value in d_values.items():
                    fields[f"{dynamic_prefix}{d_key}"] = d_value
            elif route_key.startswith("crushing.") and process_code == "FS":
                fields["工序代码"] = process_code
                fields["工序名称"] = process_name_map[process_code]

                dynamic_prefix = "粉碎"
                if sample_suffix:
                    fs_subline = self._resolve_fs_subline(sample_suffix)
                    fs_slot = self._resolve_fs_slot(sample_suffix)
                    if fs_subline:
                        dynamic_prefix = f"{dynamic_prefix}{fs_subline}"
                        fields[f"{dynamic_prefix}线别"] = fs_subline
                    if fs_slot:
                        fields[f"{dynamic_prefix}机位"] = fs_slot
                    fields[f"{dynamic_prefix}样品段"] = sample_suffix

                if hold_minutes:
                    try:
                        fields[f"{dynamic_prefix}研磨时间(min)"] = int(hold_minutes)
                    except Exception:
                        fields[f"{dynamic_prefix}研磨时间(min)"] = hold_minutes

                for d_key, d_value in d_values.items():
                    fields[f"{dynamic_prefix}{d_key}"] = d_value
                # Keep legacy columns for backward compatibility.
                fields.update(d_values)
            else:
                fields["工序代码"] = process_code
                fields["工序名称"] = process_name_map[process_code]
                if sample_suffix:
                    fields["样品段"] = sample_suffix
                if hold_minutes:
                    try:
                        fields["研磨时间(min)"] = int(hold_minutes)
                    except Exception:
                        fields["研磨时间(min)"] = hold_minutes
                fields.update(d_values)

            records.append(
                ParsedRecord(
                    scenario="particle_size",
                    line=line,
                    batch_id=batch_id,
                    route_key=route_key,
                    fields=fields,
                )
            )

        return records

    def _parse_xm_solids(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("particle_size", True):
            return []

        normalized_text = self._normalize_dash(text)
        process_name_map = self._particle_process_name_map()
        wet_prefix_map = self._wet_process_field_prefix_map()
        prefix = wet_prefix_map.get("XM", "细磨")
        line_pattern = self._production_line_pattern()

        solids_regex = re.compile(
            rf"(S\d+)\s*-\s*XM\s*-\s*D([{line_pattern}])(\d{{4}})\s*-\s*(\d+)"
            r"(?:\s*-\s*([A-Z0-9]+))?"
            r"(?:\s*-\s*(\d+)\s*MIN)?"
            r"\s*[：:]\s*(\d+(?:[.,]\d+)?)\s*[％%]\s*DC",
            re.IGNORECASE,
        )

        xm_suffix_hints: dict[tuple[str, str, str, str], tuple[str, str]] = {}
        records: list[ParsedRecord] = []
        for match in solids_regex.finditer(normalized_text):
            material_type = str(match.group(1)).upper().strip()
            line = str(match.group(2)).upper().strip()
            date_code = str(match.group(3)).strip()
            seq = str(match.group(4)).strip()
            sample_suffix = str(match.group(5) or "").upper().strip()
            hold_minutes = str(match.group(6) or "").strip()
            sample_suffix, hold_minutes = self._normalize_sample_suffix_and_hold_minutes(sample_suffix, hold_minutes)
            solids_raw = str(match.group(7)).strip().replace(",", ".")

            batch_meta_key = (material_type, line, date_code, seq)
            if sample_suffix:
                hinted_hold = hold_minutes
                if not hinted_hold and batch_meta_key in xm_suffix_hints:
                    hinted_hold = xm_suffix_hints[batch_meta_key][1]
                xm_suffix_hints[batch_meta_key] = (sample_suffix, hinted_hold)
            elif batch_meta_key in xm_suffix_hints:
                hinted_suffix, hinted_hold = xm_suffix_hints[batch_meta_key]
                sample_suffix = hinted_suffix
                if not hold_minutes and hinted_hold:
                    hold_minutes = hinted_hold

            try:
                solids_value = float(solids_raw)
            except Exception:
                continue

            route_key = self._resolve_particle_route_key("XM", line)
            if route_key.startswith("wet_process."):
                batch_id = f"{material_type}-D{line}{date_code}-{seq}"
            else:
                batch_id = f"{material_type}-XM-D{line}{date_code}-{seq}"

            fields: dict[str, Any] = {
                "物料类型": material_type,
                "消息时间": message_time,
            }

            if route_key.startswith("wet_process."):
                fields["最后更新工序"] = process_name_map["XM"]
                dynamic_prefix = prefix

                if sample_suffix:
                    xm_subline = self._resolve_xm_subline(sample_suffix)
                    xm_slot = self._resolve_xm_sample_slot(sample_suffix)
                    if xm_subline:
                        dynamic_prefix = f"{prefix}{xm_subline}"
                        fields[f"{dynamic_prefix}线别"] = xm_subline
                    if xm_slot:
                        fields[f"{dynamic_prefix}段位"] = xm_slot
                    fields[f"{dynamic_prefix}样品段"] = sample_suffix

                if hold_minutes:
                    try:
                        fields[f"{dynamic_prefix}研磨时间(min)"] = int(hold_minutes)
                    except Exception:
                        fields[f"{dynamic_prefix}研磨时间(min)"] = hold_minutes

                fields[f"{dynamic_prefix}固含量(%)"] = solids_value
            else:
                fields["工序代码"] = "XM"
                fields["工序名称"] = process_name_map["XM"]
                if sample_suffix:
                    fields["样品段"] = sample_suffix
                if hold_minutes:
                    try:
                        fields["研磨时间(min)"] = int(hold_minutes)
                    except Exception:
                        fields["研磨时间(min)"] = hold_minutes
                fields["固含量(%)"] = solids_value

            records.append(
                ParsedRecord(
                    scenario="particle_size",
                    line=line,
                    batch_id=batch_id,
                    route_key=route_key,
                    fields=fields,
                )
            )

        return records

    # ===== Extra rule parser (optional) =====

    @staticmethod
    def _extract_kv_pairs(text: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            for sep in ("：", ":", "="):
                if sep in line:
                    key, val = line.split(sep, 1)
                    key = key.strip()
                    val = val.strip()
                    if key and val:
                        result[key.lower()] = val
                    break
        return result

    @staticmethod
    def _extract_regex_fields(text: str, rules: list[dict[str, Any]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            field = str(rule.get("field", "")).strip()
            pattern = str(rule.get("pattern", "")).strip()
            group = rule.get("group", None)
            if not field or not pattern:
                continue

            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            except re.error:
                continue
            if not match:
                continue

            extracted: str | None = None
            if group is not None:
                try:
                    extracted = str(match.group(group)).strip()
                except Exception:
                    extracted = None
            else:
                named = match.groupdict()
                if named:
                    for _, value in named.items():
                        if value is not None and str(value).strip():
                            extracted = str(value).strip()
                            break
                if extracted is None and match.groups():
                    extracted = str(match.group(1)).strip()
                if extracted is None:
                    extracted = str(match.group(0)).strip()

            if extracted:
                result[field] = extracted
        return result

    def _extract_extra_fields(self, full_text: str) -> tuple[dict[str, Any], bool]:
        rules = self._get_json_config("rules_json", {})
        fields: dict[str, Any] = {}
        matched = False

        constant_fields = rules.get("constant_fields", {})
        if isinstance(constant_fields, dict):
            for k, v in constant_fields.items():
                key = str(k).strip()
                if key:
                    fields[key] = v
                    matched = True

        kv_aliases = rules.get("kv_aliases", {})
        if isinstance(kv_aliases, dict):
            kv_pairs = self._extract_kv_pairs(full_text)
            for target_field, aliases_value in kv_aliases.items():
                tf = str(target_field).strip()
                if not tf:
                    continue
                aliases: list[str] = []
                if isinstance(aliases_value, str):
                    aliases = [aliases_value]
                elif isinstance(aliases_value, list):
                    aliases = [str(item) for item in aliases_value]

                for alias in aliases:
                    normalized = alias.strip().lower()
                    if normalized and normalized in kv_pairs:
                        fields[tf] = kv_pairs[normalized]
                        matched = True
                        break

        regex_rules = rules.get("regex_extractors", [])
        if isinstance(regex_rules, list):
            regex_fields = self._extract_regex_fields(full_text, regex_rules)
            if regex_fields:
                fields.update(regex_fields)
                matched = True

        return fields, matched

    # ===== Bitable write =====

    def _resolve_table_id(self, route_key: str) -> str:
        routing = self._get_json_config("table_routing_json", {})
        if route_key in routing and str(routing.get(route_key, "")).strip():
            return str(routing[route_key]).strip()

        prefix = route_key.split(".", 1)[0]
        if prefix in routing and str(routing.get(prefix, "")).strip():
            return str(routing[prefix]).strip()

        return ""

    async def _resolve_or_create_table_id(self, route_key: str) -> str:
        override_table_id = self._route_table_override.get(route_key, "")
        if override_table_id:
            return override_table_id

        explicit_table_id = self._resolve_table_id(route_key)
        if explicit_table_id:
            return explicit_table_id

        cached = self._route_table_cache.get(route_key, "")
        if cached:
            return cached

        if not self._get_bool_config("auto_create_table_by_route", False):
            return ""

        table_name = self._resolve_table_name(route_key)
        table_id = await self._get_or_create_table_id_by_name(table_name)
        if table_id:
            self._route_table_cache[route_key] = table_id
            return table_id

        return self._get_str_config("bitable_default_table_id", "")

    @staticmethod
    def _is_table_id_not_found_error(detail: str) -> bool:
        text = str(detail or "").strip().lower()
        if not text:
            return False
        if "tableidnotfound" in text:
            return True
        if "code=1254041" in text:
            return True
        return False

    @staticmethod
    def _is_record_id_not_found_error(detail: str) -> bool:
        text = str(detail or "").strip().lower()
        if not text:
            return False
        if "recordidnotfound" in text:
            return True
        if "record id not found" in text:
            return True
        if "record_id not found" in text:
            return True
        if "record not found" in text:
            return True
        return False

    def _invalidate_table_runtime_cache(self, route_key: str, table_id: str) -> None:
        self._route_table_cache.pop(route_key, None)
        self._route_table_override.pop(route_key, None)

        table_name = self._resolve_table_name(route_key)
        if table_name:
            self._table_name_to_id_cache.pop(table_name, None)

        if table_id:
            stale_names = [name for name, tid in self._table_name_to_id_cache.items() if tid == table_id]
            for name in stale_names:
                self._table_name_to_id_cache.pop(name, None)

            self._table_field_types_cache.pop(table_id, None)
            stale_record_cache_keys = [key for key in self._record_lookup_cache.keys() if key.startswith(f"{table_id}:")]
            for key in stale_record_cache_keys:
                self._record_lookup_cache.pop(key, None)

    async def _rebuild_route_table_id(self, route_key: str, table_id: str) -> str:
        self._invalidate_table_runtime_cache(route_key, table_id)

        table_name = self._resolve_table_name(route_key)
        rebuilt_table_id = await self._get_or_create_table_id_by_name(table_name)
        if rebuilt_table_id:
            # Override stale explicit route mapping at runtime after table recreation.
            self._route_table_override[route_key] = rebuilt_table_id
            self._route_table_cache[route_key] = rebuilt_table_id
            return rebuilt_table_id

        fallback_table_id = self._get_str_config("bitable_default_table_id", "")
        if fallback_table_id:
            self._route_table_override[route_key] = fallback_table_id
        return fallback_table_id

    async def _write_record_to_bitable(self, table_id: str, fields: dict[str, Any]) -> tuple[bool, str]:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token or not table_id:
            return False, "bitable_app_token or table_id is empty"

        endpoint_template = self._get_str_config(
            "bitable_endpoint_template",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
        )
        endpoint = endpoint_template.format(app_token=app_token, table_id=table_id)

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {"fields": fields}

        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            return False, f"bitable write failed, HTTP {response.status_code}: {response.text[:300]}"

        try:
            body = response.json()
        except Exception:
            return False, f"bitable write failed, non-JSON response: {response.text[:300]}"

        code = int(body.get("code", 0))
        if code != 0:
            return False, f"bitable write failed, code={code}, msg={body.get('msg', '')}"

        data = body.get("data", {}) or {}
        record = data.get("record", {}) or {}
        record_id = ""
        if isinstance(record, dict):
            record_id = str(record.get("record_id", "")).strip()

        return True, record_id

    async def _update_record_to_bitable(self, table_id: str, record_id: str, fields: dict[str, Any]) -> tuple[bool, str]:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token or not table_id or not record_id:
            return False, "bitable_app_token/table_id/record_id is empty"

        endpoint = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
        )
        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {"fields": fields}

        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.put(endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            return False, f"bitable update failed, HTTP {response.status_code}: {response.text[:300]}"

        try:
            body = response.json()
        except Exception:
            return False, f"bitable update failed, non-JSON response: {response.text[:300]}"

        code = int(body.get("code", 0))
        if code != 0:
            return False, f"bitable update failed, code={code}, msg={body.get('msg', '')}"

        return True, record_id

    def _build_record_lookup_cache_key(self, table_id: str, match_fields: dict[str, str]) -> str:
        return f"{table_id}:{json.dumps(match_fields, ensure_ascii=False, sort_keys=True)}"

    @staticmethod
    def _field_to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, sort_keys=True)
            except Exception:
                return str(value).strip()
        return str(value).strip()

    @staticmethod
    def _dump_json_text(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return "{}"

    @staticmethod
    def _load_json_object(raw: Any) -> dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    def _build_history_write_fields(
        self,
        source_message_id: str,
        table_id: str,
        upsert_result: UpsertResult,
        record: ParsedRecord,
        note: str = "",
    ) -> dict[str, Any]:
        fields = self._history_field_names()
        return {
            fields["source_message_id"]: source_message_id,
            fields["target_table_id"]: table_id,
            fields["target_record_id"]: upsert_result.record_id,
            fields["operation"]: upsert_result.operation or "unknown",
            fields["before_fields_json"]: self._dump_json_text(upsert_result.before_fields),
            fields["after_fields_json"]: self._dump_json_text(upsert_result.after_fields),
            fields["route_key"]: record.route_key,
            fields["batch_id"]: record.batch_id,
            fields["line"]: record.line,
            fields["logged_at_ts"]: str(time.time_ns()),
            fields["status"]: "applied",
            fields["note"]: note,
        }

    async def _find_record_item_by_record_id(self, table_id: str, record_id: str) -> dict[str, Any] | None:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token or not table_id or not record_id:
            return None

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

        page_token = ""
        scanned = 0
        scan_limit = self._get_int_config("upsert_scan_limit", 1000, min_value=100, max_value=5000)
        page_size = 200

        while scanned < scan_limit:
            query: dict[str, Any] = {"page_size": page_size}
            if page_token:
                query["page_token"] = page_token

            data = await self._call_feishu_json_api("GET", endpoint, headers=headers, params=query)
            items = data.get("items", []) or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                current_record_id = str(item.get("record_id", "")).strip()
                if current_record_id == record_id:
                    return item

            scanned += len(items)
            if not bool(data.get("has_more", False)):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break

        return None

    async def _find_record_items_by_field(
        self,
        table_id: str,
        field_name: str,
        field_value: str,
        *,
        scan_limit: int,
        match_limit: int,
    ) -> list[dict[str, Any]]:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token or not table_id or not field_name or not field_value:
            return []

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

        page_token = ""
        scanned = 0
        page_size = 200
        expected_value = self._field_to_text(field_value)
        matched_items: list[dict[str, Any]] = []

        while scanned < scan_limit and len(matched_items) < match_limit:
            query: dict[str, Any] = {"page_size": page_size}
            if page_token:
                query["page_token"] = page_token

            data = await self._call_feishu_json_api("GET", endpoint, headers=headers, params=query)
            items = data.get("items", []) or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                fields = item.get("fields", {}) or {}
                if not isinstance(fields, dict):
                    continue

                current_value = self._field_to_text(fields.get(field_name))
                if current_value == expected_value:
                    matched_items.append(item)
                    if len(matched_items) >= match_limit:
                        break

            scanned += len(items)
            if not bool(data.get("has_more", False)):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break

        return matched_items

    async def _record_history_entry(
        self,
        source_message_id: str,
        table_id: str,
        record: ParsedRecord,
        upsert_result: UpsertResult,
    ) -> tuple[bool, str]:
        if not source_message_id:
            return False, "source_message_id is empty"

        history_table_id = await self._resolve_history_table_id()
        if not history_table_id:
            return False, "history_table_id is empty"

        write_fields = self._build_history_write_fields(source_message_id, table_id, upsert_result, record)
        ok_fields, detail_fields, field_types = await self._ensure_table_fields(history_table_id, write_fields)
        if not ok_fields:
            return False, detail_fields

        normalized_fields = self._normalize_write_fields(write_fields, field_types)
        return await self._write_record_to_bitable(history_table_id, normalized_fields)

    def _parse_history_entry(self, item: dict[str, Any]) -> RecallHistoryEntry | None:
        record_id = str(item.get("record_id", "")).strip()
        fields = item.get("fields", {}) or {}
        if not record_id or not isinstance(fields, dict):
            return None

        names = self._history_field_names()
        raw_logged_at = self._field_to_text(fields.get(names["logged_at_ts"]))
        try:
            logged_at_ts = int(raw_logged_at)
        except Exception:
            logged_at_ts = 0

        return RecallHistoryEntry(
            history_record_id=record_id,
            source_message_id=self._field_to_text(fields.get(names["source_message_id"])),
            target_table_id=self._field_to_text(fields.get(names["target_table_id"])),
            target_record_id=self._field_to_text(fields.get(names["target_record_id"])),
            operation=self._field_to_text(fields.get(names["operation"])).lower(),
            before_fields=self._load_json_object(fields.get(names["before_fields_json"])),
            after_fields=self._load_json_object(fields.get(names["after_fields_json"])),
            route_key=self._field_to_text(fields.get(names["route_key"])),
            batch_id=self._field_to_text(fields.get(names["batch_id"])),
            line=self._field_to_text(fields.get(names["line"])),
            logged_at_ts=logged_at_ts,
            status=self._field_to_text(fields.get(names["status"])).lower(),
        )

    async def _find_history_entries_by_source_message_id(self, source_message_id: str) -> tuple[str, list[RecallHistoryEntry]]:
        history_table_id = await self._resolve_history_table_id()
        if not history_table_id or not source_message_id:
            return history_table_id, []

        names = self._history_field_names()
        items = await self._find_record_items_by_field(
            history_table_id,
            names["source_message_id"],
            source_message_id,
            scan_limit=self._get_int_config("recall_scan_limit", 1000, min_value=100, max_value=5000),
            match_limit=self._get_int_config("recall_match_limit", 50, min_value=1, max_value=200),
        )
        entries = [entry for entry in (self._parse_history_entry(item) for item in items) if entry is not None]
        entries.sort(key=lambda item: item.logged_at_ts, reverse=True)
        return history_table_id, entries

    async def _find_history_entries_by_target_record(
        self,
        history_table_id: str,
        target_table_id: str,
        target_record_id: str,
    ) -> list[RecallHistoryEntry]:
        if not history_table_id or not target_record_id:
            return []

        names = self._history_field_names()
        items = await self._find_record_items_by_field(
            history_table_id,
            names["target_record_id"],
            target_record_id,
            scan_limit=self._get_int_config("recall_scan_limit", 1000, min_value=100, max_value=5000),
            match_limit=200,
        )
        entries = [entry for entry in (self._parse_history_entry(item) for item in items) if entry is not None]
        entries = [entry for entry in entries if entry.target_table_id == target_table_id]
        entries.sort(key=lambda item: item.logged_at_ts, reverse=True)
        return entries

    async def _update_history_entry_status(
        self,
        history_table_id: str,
        history_record_id: str,
        status: str,
        note: str = "",
    ) -> tuple[bool, str]:
        names = self._history_field_names()
        write_fields = {
            names["status"]: status,
            names["note"]: note,
        }
        ok_fields, detail_fields, field_types = await self._ensure_table_fields(history_table_id, write_fields)
        if not ok_fields:
            return False, detail_fields

        normalized_fields = self._normalize_write_fields(write_fields, field_types)
        return await self._update_record_to_bitable(history_table_id, history_record_id, normalized_fields)

    def _collect_recall_candidate_table_ids(self, source_message_id: str) -> list[str]:
        table_ids: list[str] = []
        visited: set[str] = set()

        def _append_table_id(raw: Any) -> None:
            tid = str(raw or "").strip()
            if not tid or tid in visited:
                return
            visited.add(tid)
            table_ids.append(tid)

        for table_id, _record_id in self._source_record_cache.get(source_message_id, []):
            _append_table_id(table_id)

        routing = self._get_json_config("table_routing_json", {})
        for table_id in routing.values():
            _append_table_id(table_id)

        for table_id in self._route_table_cache.values():
            _append_table_id(table_id)
        for table_id in self._route_table_override.values():
            _append_table_id(table_id)
        for table_id in self._table_name_to_id_cache.values():
            _append_table_id(table_id)

        _append_table_id(self._get_str_config("bitable_default_table_id", ""))
        return table_ids

    async def _find_record_ids_by_field(self, table_id: str, field_name: str, field_value: str) -> list[str]:
        items = await self._find_record_items_by_field(
            table_id,
            field_name,
            field_value,
            scan_limit=self._get_int_config("recall_scan_limit", 1000, min_value=100, max_value=5000),
            match_limit=self._get_int_config("recall_match_limit", 50, min_value=1, max_value=200),
        )
        record_ids: list[str] = []
        for item in items:
            record_id = str(item.get("record_id", "")).strip()
            if record_id:
                record_ids.append(record_id)
        return record_ids

    def _build_recall_write_fields(self, recall_meta: dict[str, str]) -> dict[str, Any]:
        fields: dict[str, Any] = {}

        flag_field = self._get_str_config("recalled_flag_field", "是否撤回")
        if flag_field:
            fields[flag_field] = self._get_str_config("recalled_flag_value", "是")

        time_field = self._get_str_config("recalled_time_field", "撤回时间")
        if time_field:
            recall_time = self._format_time_value(recall_meta.get("recall_time", ""), fallback_now=True)
            fields[time_field] = recall_time

        type_field = self._get_str_config("recalled_type_field", "撤回类型")
        if type_field:
            fields[type_field] = recall_meta.get("recall_type", "").strip() or "unknown"

        return fields

    @staticmethod
    def _is_history_entry_applied(status: str) -> bool:
        normalized = str(status or "").strip().lower()
        return normalized in {"", "applied"}

    async def _handle_recalled_message_from_history(
        self,
        source_message_id: str,
        recall_meta: dict[str, str],
    ) -> tuple[bool, int, int, list[str]]:
        try:
            history_table_id, history_entries = await self._find_history_entries_by_source_message_id(source_message_id)
        except Exception as exc:
            return False, 0, 0, [f"load recall history failed: {exc}"]

        if not history_table_id or not history_entries:
            return False, 0, 0, []

        recall_fields = self._build_recall_write_fields(recall_meta)
        success_updates = 0
        matched_records = 0
        errors: list[str] = []

        for entry in history_entries:
            if not entry.target_table_id or not entry.target_record_id:
                errors.append(f"history={entry.history_record_id}, target record is empty")
                continue

            matched_records += 1
            if not self._is_history_entry_applied(entry.status):
                errors.append(f"history={entry.history_record_id}, recall history already handled")
                continue

            try:
                sibling_entries = await self._find_history_entries_by_target_record(
                    history_table_id,
                    entry.target_table_id,
                    entry.target_record_id,
                )
            except Exception as exc:
                errors.append(
                    f"table={entry.target_table_id}, record={entry.target_record_id}, load target history failed: {exc}"
                )
                continue

            latest_applied = next((item for item in sibling_entries if self._is_history_entry_applied(item.status)), None)
            if latest_applied is None or latest_applied.history_record_id != entry.history_record_id:
                note = "skipped restore because newer write exists"
                ok_status, detail_status = await self._update_history_entry_status(
                    history_table_id,
                    entry.history_record_id,
                    "recalled_skipped_not_latest",
                    note,
                )
                if not ok_status:
                    errors.append(f"history={entry.history_record_id}, {detail_status}")
                errors.append(
                    f"table={entry.target_table_id}, record={entry.target_record_id}, newer write exists, skip restore"
                )
                continue

            restore_fields = dict(entry.before_fields)
            restore_operation = entry.operation == "update" and bool(restore_fields)

            if restore_operation:
                ok_fields, detail_fields, field_types = await self._ensure_table_fields(entry.target_table_id, restore_fields)
                if not ok_fields:
                    errors.append(f"table={entry.target_table_id}, record={entry.target_record_id}, {detail_fields}")
                    continue
                normalized_fields = self._normalize_write_fields(restore_fields, field_types)
                ok_update, detail_update = await self._update_record_to_bitable(
                    entry.target_table_id,
                    entry.target_record_id,
                    normalized_fields,
                )
                if not ok_update:
                    errors.append(f"table={entry.target_table_id}, record={entry.target_record_id}, {detail_update}")
                    continue

                success_updates += 1
                ok_status, detail_status = await self._update_history_entry_status(
                    history_table_id,
                    entry.history_record_id,
                    "recalled_restored",
                    "restored previous fields",
                )
                if not ok_status:
                    errors.append(f"history={entry.history_record_id}, {detail_status}")
                continue

            ok_fields, detail_fields, field_types = await self._ensure_table_fields(entry.target_table_id, recall_fields)
            if not ok_fields:
                errors.append(f"table={entry.target_table_id}, record={entry.target_record_id}, {detail_fields}")
                continue
            normalized_recall_fields = self._normalize_write_fields(recall_fields, field_types)
            ok_mark, detail_mark = await self._update_record_to_bitable(
                entry.target_table_id,
                entry.target_record_id,
                normalized_recall_fields,
            )
            if not ok_mark:
                errors.append(f"table={entry.target_table_id}, record={entry.target_record_id}, {detail_mark}")
                continue

            success_updates += 1
            ok_status, detail_status = await self._update_history_entry_status(
                history_table_id,
                entry.history_record_id,
                "recalled_marked",
                "no previous fields, fallback to recall mark",
            )
            if not ok_status:
                errors.append(f"history={entry.history_record_id}, {detail_status}")

        return True, matched_records, success_updates, errors

    async def _mark_recalled_message_directly(
        self,
        source_message_id: str,
        recall_meta: dict[str, str],
    ) -> tuple[int, int, list[str]]:
        source_field = self._get_str_config("source_message_id_field", "源消息ID")
        if not source_field or not source_message_id:
            return 0, 0, []

        candidate_table_ids = self._collect_recall_candidate_table_ids(source_message_id)
        if self._get_bool_config("recall_scan_all_tables", True):
            try:
                all_tables = await self._list_all_bitable_tables()
                for table in all_tables:
                    tid = str(table.get("table_id", "")).strip()
                    if tid and tid not in candidate_table_ids:
                        candidate_table_ids.append(tid)
            except Exception:
                pass

        if not candidate_table_ids:
            return 0, 0, [f"未找到可扫描的数据表，message_id={source_message_id}"]

        preferred_records = self._source_record_cache.get(source_message_id, [])
        recall_fields = self._build_recall_write_fields(recall_meta)
        success_updates = 0
        errors: list[str] = []
        matched_records = 0

        for table_id in candidate_table_ids:
            record_ids = [rid for tid, rid in preferred_records if tid == table_id and rid]
            if not record_ids:
                try:
                    record_ids = await self._find_record_ids_by_field(table_id, source_field, source_message_id)
                except Exception as exc:
                    errors.append(f"table={table_id}, find records failed: {exc}")
                    continue

            if not record_ids:
                continue

            matched_records += len(record_ids)
            ok_fields, detail_fields, field_types = await self._ensure_table_fields(table_id, recall_fields)
            if not ok_fields:
                errors.append(f"table={table_id}, {detail_fields}")
                continue
            normalized_fields = self._normalize_write_fields(recall_fields, field_types)

            for record_id in record_ids:
                ok, detail = await self._update_record_to_bitable(table_id, record_id, normalized_fields)
                if ok:
                    success_updates += 1
                    self._remember_written_record(source_message_id, table_id, record_id)
                else:
                    errors.append(f"table={table_id}, record={record_id}, {detail}")

        return matched_records, success_updates, errors

    async def _handle_recalled_message(self, event_ctx: context.EventContext, recall_meta: dict[str, str]) -> None:
        if not self._get_bool_config("enable_recall_revert", True):
            return

        source_message_id = recall_meta.get("message_id", "").strip()
        if not source_message_id:
            return

        matched_records = 0
        success_updates = 0
        errors: list[str] = []
        used_history = False

        if self._get_bool_config("enable_recall_restore_previous", True):
            used_history, matched_records, success_updates, errors = await self._handle_recalled_message_from_history(
                source_message_id,
                recall_meta,
            )

        if not used_history:
            direct_matched_records, direct_success_updates, direct_errors = await self._mark_recalled_message_directly(
                source_message_id,
                recall_meta,
            )
            matched_records = direct_matched_records
            success_updates = direct_success_updates
            errors.extend(direct_errors)

        if success_updates > 0:
            need_feedback = self._get_bool_config("reply_on_recall", False)
            if self._is_group_event(event_ctx) and self._get_bool_config("private_notify_on_write", True):
                need_feedback = True
            if need_feedback:
                text = f"已处理撤回：message_id={source_message_id}，匹配{matched_records}条，更新{success_updates}条。"
                if errors and self._get_bool_config("reply_on_error", False):
                    text = f"{text}\n部分失败: {self._truncate_text('; '.join(errors), 500)}"
                await self._send_feedback(event_ctx, self._truncate_text(text, 1800), is_error=False)
            return

        if not errors:
            errors.append(f"未找到可回滚记录，message_id={source_message_id}")
        need_error_feedback = self._get_bool_config("reply_on_error", False)
        if self._is_group_event(event_ctx) and self._get_bool_config("private_notify_on_error", True):
            need_error_feedback = True
        if need_error_feedback:
            err_text = self._truncate_text("; ".join(errors), 1000)
            await self._send_feedback(event_ctx, f"撤回处理失败: {err_text}", is_error=True)

    async def _find_existing_record_id(
        self,
        table_id: str,
        match_fields: dict[str, str],
        *,
        use_cache: bool = True,
    ) -> str:
        if not match_fields:
            return ""

        cache_key = self._build_record_lookup_cache_key(table_id, match_fields)
        if use_cache:
            cached = self._record_lookup_cache.get(cache_key, "")
            if cached:
                return cached

        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token:
            return ""

        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            record_id = await self._search_existing_record_id(table_id, match_fields, headers)
            if record_id:
                self._record_lookup_cache[cache_key] = record_id
                return record_id
        except Exception:
            pass

        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

        page_token = ""
        scanned = 0
        scan_limit = self._get_int_config("upsert_scan_limit", 1000, min_value=100, max_value=5000)
        page_size = 200
        expected = {k: self._field_to_text(v) for k, v in match_fields.items() if k}

        while scanned < scan_limit:
            query: dict[str, Any] = {"page_size": page_size}
            if page_token:
                query["page_token"] = page_token

            data = await self._call_feishu_json_api("GET", endpoint, headers=headers, params=query)
            items = data.get("items", []) or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                record_id = str(item.get("record_id", "")).strip()
                fields = item.get("fields", {}) or {}
                if not record_id or not isinstance(fields, dict):
                    continue

                matched = True
                for field_name, expected_value in expected.items():
                    current_value = self._field_to_text(fields.get(field_name))
                    if current_value != expected_value:
                        matched = False
                        break

                if matched:
                    self._record_lookup_cache[cache_key] = record_id
                    return record_id

            scanned += len(items)
            if not bool(data.get("has_more", False)):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break

        return ""

    async def _search_existing_record_id(
        self,
        table_id: str,
        match_fields: dict[str, str],
        headers: dict[str, str],
    ) -> str:
        app_token = self._get_str_config("bitable_app_token", "")
        if not app_token or not table_id or not match_fields:
            return ""

        endpoint = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
        conditions = [
            {"field_name": field_name, "operator": "is", "value": [self._field_to_text(value)]}
            for field_name, value in match_fields.items()
            if field_name and self._field_to_text(value)
        ]
        if not conditions:
            return ""

        payload = {
            "automatic_fields": False,
            "filter": {
                "conjunction": "and",
                "conditions": conditions,
            },
        }
        data = await self._call_feishu_json_api(
            "POST",
            endpoint,
            headers=headers,
            payload=payload,
            params={"page_size": 1},
        )
        items = data.get("items", []) or []
        for item in items:
            if not isinstance(item, dict):
                continue
            record_id = str(item.get("record_id", "")).strip()
            if record_id:
                return record_id
        return ""

    def _build_upsert_match_fields(self, write_fields: dict[str, Any]) -> dict[str, str]:
        if not self._get_bool_config("upsert_by_batch", True):
            return {}

        batch_field = self._get_str_config("batch_field", "批次号")
        if not batch_field:
            return {}
        batch_value = self._field_to_text(write_fields.get(batch_field))
        if not batch_value:
            return {}

        match_fields: dict[str, str] = {batch_field: batch_value}

        if self._get_bool_config("upsert_match_include_route", True):
            route_field = self._get_str_config("route_field", "路由")
            route_value = self._field_to_text(write_fields.get(route_field))
            if route_field and route_value:
                match_fields[route_field] = route_value

        if self._get_bool_config("upsert_match_include_line", True):
            line_field = self._get_str_config("line_field", "产线")
            line_value = self._field_to_text(write_fields.get(line_field))
            if line_field and line_value:
                match_fields[line_field] = line_value

        return match_fields

    async def _upsert_record_to_bitable(
        self,
        table_id: str,
        fields: dict[str, Any],
        match_fields: dict[str, str],
    ) -> UpsertResult:
        if not self._get_bool_config("upsert_by_batch", True):
            ok, detail = await self._write_record_to_bitable(table_id, fields)
            return UpsertResult(
                ok=ok,
                detail=detail,
                record_id=detail if ok else "",
                operation="create",
                before_fields={},
                after_fields=dict(fields),
            )

        if not match_fields:
            ok, detail = await self._write_record_to_bitable(table_id, fields)
            return UpsertResult(
                ok=ok,
                detail=detail,
                record_id=detail if ok else "",
                operation="create",
                before_fields={},
                after_fields=dict(fields),
            )

        try:
            existing_id = await self._find_existing_record_id(table_id, match_fields)
        except Exception as exc:
            return UpsertResult(
                ok=False,
                detail=f"find existing record failed: {exc}",
                record_id="",
                operation="",
                before_fields={},
                after_fields=dict(fields),
            )

        if existing_id:
            before_fields: dict[str, Any] = {}
            try:
                record_item = await self._find_record_item_by_record_id(table_id, existing_id)
                if record_item is not None:
                    existing_fields = record_item.get("fields", {}) or {}
                    if isinstance(existing_fields, dict):
                        before_fields = dict(existing_fields)
            except Exception:
                before_fields = {}

            ok, detail = await self._update_record_to_bitable(table_id, existing_id, fields)
            if ok:
                cache_key = self._build_record_lookup_cache_key(table_id, match_fields)
                self._record_lookup_cache[cache_key] = existing_id
                return UpsertResult(
                    ok=True,
                    detail=detail,
                    record_id=existing_id,
                    operation="update",
                    before_fields=before_fields,
                    after_fields=dict(fields),
                )

            if not self._is_record_id_not_found_error(detail):
                return UpsertResult(
                    ok=ok,
                    detail=detail,
                    record_id=existing_id,
                    operation="update",
                    before_fields=before_fields,
                    after_fields=dict(fields),
                )

            cache_key = self._build_record_lookup_cache_key(table_id, match_fields)
            self._record_lookup_cache.pop(cache_key, None)

            try:
                refreshed_existing_id = await self._find_existing_record_id(
                    table_id,
                    match_fields,
                    use_cache=False,
                )
            except Exception as exc:
                return UpsertResult(
                    ok=False,
                    detail=f"refresh existing record failed: {exc}",
                    record_id="",
                    operation="",
                    before_fields={},
                    after_fields=dict(fields),
                )

            if refreshed_existing_id:
                before_fields_retry: dict[str, Any] = {}
                try:
                    refreshed_item = await self._find_record_item_by_record_id(table_id, refreshed_existing_id)
                    if refreshed_item is not None:
                        refreshed_fields = refreshed_item.get("fields", {}) or {}
                        if isinstance(refreshed_fields, dict):
                            before_fields_retry = dict(refreshed_fields)
                except Exception:
                    before_fields_retry = {}

                ok_retry, detail_retry = await self._update_record_to_bitable(table_id, refreshed_existing_id, fields)
                if ok_retry:
                    self._record_lookup_cache[cache_key] = refreshed_existing_id
                    return UpsertResult(
                        ok=True,
                        detail=detail_retry,
                        record_id=refreshed_existing_id,
                        operation="update",
                        before_fields=before_fields_retry,
                        after_fields=dict(fields),
                    )
                if not self._is_record_id_not_found_error(detail_retry):
                    return UpsertResult(
                        ok=ok_retry,
                        detail=detail_retry,
                        record_id=refreshed_existing_id,
                        operation="update",
                        before_fields=before_fields_retry,
                        after_fields=dict(fields),
                    )
                self._record_lookup_cache.pop(cache_key, None)

        ok, detail = await self._write_record_to_bitable(table_id, fields)
        if ok:
            cache_key = self._build_record_lookup_cache_key(table_id, match_fields)
            if detail:
                self._record_lookup_cache[cache_key] = detail
        return UpsertResult(
            ok=ok,
            detail=detail,
            record_id=detail if ok else "",
            operation="create",
            before_fields={},
            after_fields=dict(fields),
        )

    @staticmethod
    def _merge_records_for_write(records: list[ParsedRecord]) -> list[ParsedRecord]:
        merged_map: dict[tuple[str, str, str], ParsedRecord] = {}
        for record in records:
            key = (record.route_key, record.batch_id, record.line)
            existing = merged_map.get(key)
            if existing is None:
                merged_map[key] = ParsedRecord(
                    scenario=record.scenario,
                    line=record.line,
                    batch_id=record.batch_id,
                    route_key=record.route_key,
                    fields=dict(record.fields),
                )
                continue

            existing.fields.update(record.fields)
            if record.scenario and record.scenario not in existing.scenario.split("+"):
                existing.scenario = f"{existing.scenario}+{record.scenario}" if existing.scenario else record.scenario
        return list(merged_map.values())

    def _apply_builtin_fields(
        self,
        target_fields: dict[str, Any],
        record: ParsedRecord,
        event_ctx: context.EventContext,
        plain_text: str,
        ocr_text: str,
        message_time: str,
    ) -> None:
        scenario_field = self._get_str_config("scenario_field", "业务类型")
        line_field = self._get_str_config("line_field", "产线")
        batch_field = self._get_str_config("batch_field", "批次号")
        route_field = self._get_str_config("route_field", "路由")

        raw_text_field = self._get_str_config("raw_text_field", "原始文本")
        ocr_text_field = self._get_str_config("ocr_text_field", "OCR文本")

        sender_field = self._get_str_config("sender_id_field", "发送者ID")
        launcher_field = self._get_str_config("launcher_id_field", "会话ID")
        launcher_type_field = self._get_str_config("launcher_type_field", "会话类型")
        timestamp_field = self._get_str_config("message_time_field", "消息时间")
        source_message_id_field = self._get_str_config("source_message_id_field", "源消息ID")

        if scenario_field:
            target_fields[scenario_field] = record.scenario
        if line_field:
            target_fields[line_field] = record.line
        if batch_field and record.batch_id:
            target_fields[batch_field] = record.batch_id
        if route_field:
            target_fields[route_field] = record.route_key

        if raw_text_field and plain_text:
            target_fields[raw_text_field] = self._truncate_text(plain_text)
        if ocr_text_field and ocr_text:
            target_fields[ocr_text_field] = self._truncate_text(ocr_text)

        if sender_field:
            target_fields[sender_field] = str(getattr(event_ctx.event, "sender_id", ""))
        if launcher_field:
            target_fields[launcher_field] = str(getattr(event_ctx.event, "launcher_id", ""))
        if launcher_type_field:
            target_fields[launcher_type_field] = str(getattr(event_ctx.event, "launcher_type", ""))
        if timestamp_field:
            target_fields[timestamp_field] = message_time
        if source_message_id_field:
            source_message_id = self._extract_message_source_id(getattr(event_ctx.event, "message_chain", None))
            if source_message_id:
                target_fields[source_message_id_field] = source_message_id

    def _parse_records(self, full_text: str, message_time: str) -> list[ParsedRecord]:
        records: list[ParsedRecord] = []
        records.extend(self._parse_product(full_text, message_time))
        records.extend(self._parse_particle_size(full_text, message_time))
        records.extend(self._parse_xm_solids(full_text, message_time))
        records.extend(self._parse_spray(full_text, message_time))
        records.extend(self._parse_qqt_moisture(full_text, message_time))
        records.extend(self._parse_feeding(full_text, message_time))
        records.extend(self._parse_sintering(full_text, message_time))
        records.extend(self._parse_crushing(full_text, message_time))
        records.extend(self._parse_pure_water(full_text, message_time))
        records.extend(self._parse_kiln_batch_io(full_text, message_time))
        return records

    @staticmethod
    def _particle_d_labels() -> tuple[str, str, str, str]:
        return ("D10", "D50", "D90", "D99")

    def _extract_particle_d_values_from_fields(self, fields: dict[str, Any]) -> dict[str, Any]:
        d_values: dict[str, Any] = {}
        labels = self._particle_d_labels()

        for label in labels:
            if label in fields:
                d_values[label] = fields[label]

        for key, value in fields.items():
            upper_key = str(key).upper()
            for label in labels:
                if upper_key.endswith(label) and label not in d_values:
                    d_values[label] = value
        return d_values

    def _has_particle_d_values_in_fields(self, fields: dict[str, Any]) -> bool:
        return bool(self._extract_particle_d_values_from_fields(fields))

    def _resolve_fs_d_prefix_from_fields(self, fields: dict[str, Any]) -> str:
        for prefix in ("粉碎1线", "粉碎2线"):
            if any(str(key).startswith(prefix) for key in fields.keys()):
                return prefix

        for candidate in (fields.get("粉碎样品段"), fields.get("样品段")):
            if candidate is None:
                continue
            fs_subline = self._resolve_fs_subline(str(candidate))
            if fs_subline:
                return f"粉碎{fs_subline}"
        return "粉碎"

    def _resolve_wet_process_d_prefix_from_fields(self, fields: dict[str, Any]) -> str:
        for prefix in ("细磨1线", "细磨2线", "细磨", "粗磨", "合批"):
            if any(str(key).startswith(prefix) for key in fields.keys()):
                return prefix

        process_name = str(fields.get("最后更新工序", "")).strip()
        if "细磨" in process_name:
            for candidate in (fields.get("细磨样品段"), fields.get("样品段")):
                if candidate is None:
                    continue
                xm_subline = self._resolve_xm_subline(str(candidate))
                if xm_subline:
                    return f"细磨{xm_subline}"
            return "细磨"
        if "粗磨" in process_name:
            return "粗磨"
        if "合批" in process_name:
            return "合批"

        return ""

    def _apply_particle_d_values_to_record_fields(
        self,
        record: ParsedRecord,
        target_fields: dict[str, Any],
        d_values: dict[str, Any],
    ) -> None:
        if not d_values:
            return

        is_wet_process_record = record.route_key.startswith("wet_process")
        if is_wet_process_record:
            wet_prefix = self._resolve_wet_process_d_prefix_from_fields(target_fields)
            for label, value in d_values.items():
                key = f"{wet_prefix}{label}" if wet_prefix else label
                if key not in target_fields:
                    target_fields[key] = value
            return

        for label, value in d_values.items():
            if label not in target_fields:
                target_fields[label] = value

        process_code = str(target_fields.get("工序代码", "")).strip().upper()
        is_fs_record = process_code == "FS" or record.route_key.startswith("crushing")
        if not is_fs_record:
            return

        prefix = self._resolve_fs_d_prefix_from_fields(target_fields)
        for label, value in d_values.items():
            prefixed_key = f"{prefix}{label}"
            if prefixed_key not in target_fields:
                target_fields[prefixed_key] = value

    def _supplement_particle_records_with_ocr(
        self,
        records: list[ParsedRecord],
        ocr_text: str,
        message_time: str,
    ) -> list[ParsedRecord]:
        if not ocr_text.strip():
            return records

        ocr_particle_records = self._parse_particle_size(ocr_text, message_time)
        ocr_particle_map = {
            (item.route_key, item.batch_id, item.line): item for item in ocr_particle_records
        }
        global_ocr_d_values = self._extract_particle_d_values(ocr_text)

        supplemented: list[ParsedRecord] = []
        for record in records:
            if record.scenario != "particle_size":
                supplemented.append(record)
                continue

            merged_fields = dict(record.fields)
            key = (record.route_key, record.batch_id, record.line)
            source_record = ocr_particle_map.get(key)
            source_d_values: dict[str, Any] = {}
            if source_record is not None:
                source_d_values = self._extract_particle_d_values_from_fields(source_record.fields)
            if not source_d_values:
                source_d_values = dict(global_ocr_d_values)

            self._apply_particle_d_values_to_record_fields(record, merged_fields, source_d_values)
            supplemented.append(
                ParsedRecord(
                    scenario=record.scenario,
                    line=record.line,
                    batch_id=record.batch_id,
                    route_key=record.route_key,
                    fields=merged_fields,
                )
            )
        return supplemented

    def _merge_particle_anchor_records_with_ocr(
        self,
        anchor_records: list[ParsedRecord],
        ocr_text: str,
        message_time: str,
    ) -> list[ParsedRecord]:
        if not anchor_records:
            return []

        ocr_particle_records = self._parse_particle_size(ocr_text, message_time)
        ocr_particle_map = {
            (item.route_key, item.batch_id, item.line): item for item in ocr_particle_records
        }
        global_ocr_d_values = self._extract_particle_d_values(ocr_text)

        merged_records: list[ParsedRecord] = []
        for anchor in anchor_records:
            merged_fields = dict(anchor.fields)
            key = (anchor.route_key, anchor.batch_id, anchor.line)
            source_record = ocr_particle_map.get(key)
            source_d_values: dict[str, Any] = {}
            if source_record is not None:
                source_d_values = self._extract_particle_d_values_from_fields(source_record.fields)
            if not source_d_values:
                source_d_values = dict(global_ocr_d_values)

            self._apply_particle_d_values_to_record_fields(anchor, merged_fields, source_d_values)
            if not self._has_particle_d_values_in_fields(merged_fields):
                continue

            merged_records.append(
                ParsedRecord(
                    scenario=anchor.scenario,
                    line=anchor.line,
                    batch_id=anchor.batch_id,
                    route_key=anchor.route_key,
                    fields=merged_fields,
                )
            )
        return merged_records

    @staticmethod
    def _drop_crushing_records_if_particle_exists(records: list[ParsedRecord]) -> list[ParsedRecord]:
        particle_keys = {
            (record.route_key, record.batch_id, record.line)
            for record in records
            if record.scenario == "particle_size" and record.route_key.startswith("crushing")
        }
        if not particle_keys:
            return records

        filtered: list[ParsedRecord] = []
        for record in records:
            key = (record.route_key, record.batch_id, record.line)
            if record.scenario == "crushing" and key in particle_keys:
                continue
            filtered.append(record)
        return filtered

    def _parse_records_with_text_priority(
        self,
        plain_text: str,
        ocr_text: str,
        message_time: str,
    ) -> list[ParsedRecord]:
        plain_text = plain_text.strip()
        ocr_text = ocr_text.strip()

        plain_records = self._parse_records(plain_text, message_time) if plain_text else []
        if plain_records:
            if ocr_text:
                plain_records = self._supplement_particle_records_with_ocr(plain_records, ocr_text, message_time)

                plain_particle_anchors = self._parse_particle_size(
                    plain_text,
                    message_time,
                    allow_empty_d_values=True,
                )
                existing_particle_keys = {
                    (item.route_key, item.batch_id, item.line)
                    for item in plain_records
                    if item.scenario == "particle_size"
                }
                extra_anchors = [
                    anchor
                    for anchor in plain_particle_anchors
                    if (anchor.route_key, anchor.batch_id, anchor.line) not in existing_particle_keys
                ]
                if extra_anchors:
                    plain_records.extend(
                        self._merge_particle_anchor_records_with_ocr(extra_anchors, ocr_text, message_time)
                    )
            return self._drop_crushing_records_if_particle_exists(plain_records)

        if plain_text and ocr_text:
            plain_particle_anchors = self._parse_particle_size(
                plain_text,
                message_time,
                allow_empty_d_values=True,
            )
            if plain_particle_anchors:
                merged_records = self._merge_particle_anchor_records_with_ocr(
                    plain_particle_anchors,
                    ocr_text,
                    message_time,
                )
                if merged_records:
                    return self._drop_crushing_records_if_particle_exists(merged_records)

        if ocr_text:
            ocr_records = self._parse_records(ocr_text, message_time)
            return self._drop_crushing_records_if_particle_exists(ocr_records)
        return []

    async def _handle_normal_message(self, event_ctx: context.EventContext) -> None:
        if self._mark_query_processed(event_ctx):
            return

        recall_meta = await self._extract_recall_meta(event_ctx)
        if recall_meta is not None:
            await self._handle_recalled_message(event_ctx, recall_meta)
            if self._get_bool_config("prevent_default_on_recall", True):
                event_ctx.prevent_default()
                event_ctx.prevent_postorder()
            return

        message_chain = event_ctx.event.message_chain
        plain_text = self._extract_plain_text(message_chain)
        images = self._extract_images(message_chain)

        if not plain_text and not images:
            return

        ocr_enabled = self._get_bool_config("enable_ocr_for_images", True)
        ocr_text = ""
        ocr_errors: list[str] = []
        if images and ocr_enabled:
            ocr_texts: list[str] = []
            for idx, image in enumerate(images, start=1):
                try:
                    image_bytes = await self._get_image_bytes(image)
                    text = await self._recognize_image_bytes(image_bytes)
                    if text:
                        ocr_texts.append(text)
                except Exception as exc:
                    ocr_errors.append(f"image#{idx}: {exc}")
            if ocr_texts:
                ocr_text = "\n\n".join(ocr_texts).strip()

        full_text_parts = [plain_text.strip(), ocr_text.strip()]
        full_text = "\n".join([part for part in full_text_parts if part]).strip()
        if not full_text:
            return

        message_time = self._resolve_message_time(event_ctx)
        records = self._parse_records_with_text_priority(plain_text, ocr_text, message_time)

        # Fallback using extra rules_json if built-in parsers found nothing.
        if not records:
            extra_fields, matched = self._extract_extra_fields(full_text)
            if matched:
                records.append(
                    ParsedRecord(
                        scenario="custom",
                        line="",
                        batch_id="",
                        route_key="custom",
                        fields=extra_fields,
                    )
                )

        if not records and self._get_bool_config("write_raw_when_no_match", False):
            records.append(
                ParsedRecord(
                    scenario="raw",
                    line="",
                    batch_id="",
                    route_key="raw",
                    fields={},
                )
            )

        if not records:
            if images:
                reasons: list[str] = []
                if not ocr_enabled:
                    reasons.append("图片OCR已关闭(enable_ocr_for_images=false)")
                if ocr_errors:
                    reasons.append(f"OCR失败: {self._truncate_text('; '.join(ocr_errors), 600)}")
                elif not ocr_text:
                    reasons.append("OCR未提取到有效文本")
                else:
                    ocr_preview = self._truncate_text(ocr_text.replace("\n", " / "), 240)
                    reasons.append(f"OCR已提取文本但规则未命中(预览: {ocr_preview})")
                reasons.append("未命中任何解析规则")

                error_text = "图片消息解析失败，未写入飞书表格。"
                if reasons:
                    error_text = f"{error_text} 原因: {'；'.join(reasons)}"

                # For image messages, block default LLM fallback when parsing failed.
                event_ctx.prevent_default()
                event_ctx.prevent_postorder()
                await self._send_feedback(event_ctx, self._truncate_text(error_text, 1800), is_error=True)
            return

        records = self._merge_records_for_write(records)

        if self._get_bool_config("prevent_default_on_match", True):
            event_ctx.prevent_default()
            event_ctx.prevent_postorder()

        success_count = 0
        success_records: list[ParsedRecord] = []
        errors: list[str] = []
        if ocr_errors:
            errors.append(f"OCR失败: {self._truncate_text('; '.join(ocr_errors), 600)}")

        for record in records:
            table_id = await self._resolve_or_create_table_id(record.route_key)
            if not table_id:
                errors.append(f"route={record.route_key}, table_id not configured and auto-create disabled/failed")
                continue

            write_fields = dict(record.fields)
            self._apply_builtin_fields(write_fields, record, event_ctx, plain_text, ocr_text, message_time)
            source_message_id_field = self._get_str_config("source_message_id_field", "源消息ID")
            source_message_id = self._field_to_text(write_fields.get(source_message_id_field)) if source_message_id_field else ""
            retried_after_table_not_found = False

            while True:
                ok_fields, detail_fields, field_types = await self._ensure_table_fields(table_id, write_fields)
                if not ok_fields:
                    if (not retried_after_table_not_found) and self._is_table_id_not_found_error(detail_fields):
                        rebuilt_table_id = await self._rebuild_route_table_id(record.route_key, table_id)
                        retried_after_table_not_found = True
                        if rebuilt_table_id and rebuilt_table_id != table_id:
                            table_id = rebuilt_table_id
                            continue
                    errors.append(f"route={record.route_key}, {detail_fields}")
                    break

                normalized_write_fields = self._normalize_write_fields(write_fields, field_types)
                match_fields = self._build_upsert_match_fields(normalized_write_fields)
                upsert_result = await self._upsert_record_to_bitable(table_id, normalized_write_fields, match_fields)
                if upsert_result.ok:
                    history_failed = False
                    if source_message_id and upsert_result.record_id:
                        self._remember_written_record(source_message_id, table_id, upsert_result.record_id)
                        if self._get_bool_config("enable_recall_restore_previous", True):
                            try:
                                ok_history, detail_history = await self._record_history_entry(
                                    source_message_id,
                                    table_id,
                                    record,
                                    upsert_result,
                                )
                                if not ok_history:
                                    errors.append(f"route={record.route_key}, history={detail_history}")
                                    history_failed = True
                            except Exception as exc:
                                errors.append(f"route={record.route_key}, history write failed: {exc}")
                                history_failed = True
                    if history_failed:
                        break
                    success_count += 1
                    success_records.append(record)
                    break

                if (not retried_after_table_not_found) and self._is_table_id_not_found_error(upsert_result.detail):
                    rebuilt_table_id = await self._rebuild_route_table_id(record.route_key, table_id)
                    retried_after_table_not_found = True
                    if rebuilt_table_id and rebuilt_table_id != table_id:
                        table_id = rebuilt_table_id
                        continue

                errors.append(f"route={record.route_key}, {upsert_result.detail}")
                break

        if success_count > 0:
            need_success_feedback = self._get_bool_config("reply_on_write", False)
            if self._is_group_event(event_ctx) and self._get_bool_config("private_notify_on_write", True):
                need_success_feedback = True

            if need_success_feedback:
                detail_limit = self._get_int_config("feedback_detail_limit", 5, min_value=1, max_value=20)
                detail_lines = [f"{idx + 1}. {self._build_record_brief(record)}" for idx, record in enumerate(success_records)]
                detail_text = "\n".join(detail_lines[:detail_limit])

                template = self._get_str_config("reply_text_template", "已写入飞书表格。")
                if not template:
                    template = "已写入飞书表格。"
                feedback_text = template.replace("{count}", str(success_count))
                if "{details}" in feedback_text:
                    feedback_text = feedback_text.replace("{details}", detail_text)
                elif detail_text:
                    feedback_text = f"{feedback_text}\n{detail_text}"

                need_error_feedback = self._get_bool_config("reply_on_error", False)
                if self._is_group_event(event_ctx) and self._get_bool_config("private_notify_on_error", True):
                    need_error_feedback = True
                if errors and need_error_feedback:
                    error_text = self._truncate_text("; ".join(errors), 500)
                    feedback_text = f"{feedback_text}\n失败 {len(errors)} 条: {error_text}"

                await self._send_feedback(event_ctx, self._truncate_text(feedback_text, 1800), is_error=False)

            if self._get_bool_config("prevent_default_on_write", False):
                event_ctx.prevent_default()
                event_ctx.prevent_postorder()

        if errors and success_count <= 0:
            need_error_feedback = self._get_bool_config("reply_on_error", False)
            if self._is_group_event(event_ctx) and self._get_bool_config("private_notify_on_error", True):
                need_error_feedback = True
            if need_error_feedback:
                err = self._truncate_text("; ".join(errors), 1000)
                await self._send_feedback(event_ctx, f"写入飞书表格失败: {err}", is_error=True)


