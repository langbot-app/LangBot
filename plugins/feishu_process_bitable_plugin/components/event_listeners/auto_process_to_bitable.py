from __future__ import annotations

import asyncio
import base64
import datetime
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


class AutoProcessToBitableListener(EventListener):
    def __init__(self):
        super().__init__()
        self._tenant_access_token: str = ""
        self._tenant_access_token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self._table_lock = asyncio.Lock()
        self._field_lock = asyncio.Lock()
        self._route_table_cache: dict[str, str] = {}
        self._table_name_to_id_cache: dict[str, str] = {}
        self._table_field_types_cache: dict[str, dict[str, int]] = {}

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

    def _get_bitable_app_token(self) -> str:
        return self._get_str_config("bitable_app_token", "")

    @staticmethod
    def _default_table_names() -> dict[str, str]:
        return {
            "spray.A": "A线喷雾汇总",
            "spray.B": "B线喷雾汇总",
            "feeding.A": "A线投料汇总",
            "feeding.B": "B线投料汇总",
            "sintering.A": "A线烧结汇总",
            "sintering.B": "B线烧结汇总",
            "crushing.A": "A线粉碎压实汇总",
            "crushing.B": "B线粉碎压实汇总",
            "particle_size.FS": "粉碎工序粒度汇总",
            "particle_size.CM": "粗磨工序粒度汇总",
            "particle_size.XM": "细磨工序粒度汇总",
            "particle_size.HP": "合批工序粒度汇总",
            "particle_size.QQT": "喷雾工序粒度汇总",
            "particle_size": "粒度数据汇总",
            "pure_water.A": "A线纯水PH汇总",
            "pure_water.B": "B线纯水PH汇总",
            "pure_water": "车间纯水PH汇总",
            "custom": "自定义消息汇总",
            "raw": "原始消息汇总",
        }

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
        if prefix in defaults:
            return defaults[prefix]

        if "." in route_key:
            part_a, part_b = route_key.split(".", 1)
            if part_b in {"A", "B"}:
                return f"{part_b}线{part_a}汇总"
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

            if not self._get_bool_config("auto_create_table_by_route", True):
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

            if not self._get_bool_config("auto_create_fields", True):
                return True, "", field_types

            missing = [name for name in write_fields.keys() if name and name not in field_types]
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

        if candidate is None:
            return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")

        try:
            ts = float(candidate)
            if ts > 1e12:
                ts = ts / 1000.0
            if ts > 0:
                return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).astimezone().isoformat(
                    timespec="seconds"
                )
        except Exception:
            pass

        return str(candidate)

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
    def _mark_query_processed(event_ctx: context.EventContext) -> bool:
        query = getattr(event_ctx.event, "query", None)
        if query is None:
            return False

        variables = getattr(query, "variables", None)
        if not isinstance(variables, dict):
            return False

        marker_key = "_feishu_process_bitable_processed"
        if variables.get(marker_key, False):
            return True
        variables[marker_key] = True
        return False

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
                "pure_water": True,
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
        main_regex = re.compile(
            r"([AB])\s*线\s*喷雾\s*批次(?:号)?\s*[:：]?\s*"
            r"(S\d+(?:-[A-Z]{2})?-D[AB]\d{4}-\d+(?:-?[AB]\d)?)",
            re.IGNORECASE,
        )
        params_regex = re.compile(r"([\u4e00-\u9fa5]+)\s*[:：]?\s*(\d+\.?\d*)")
        required_params = {"开度", "进口温度", "出口温度", "雾化轮转速", "水分"}

        records: list[ParsedRecord] = []
        for match in main_regex.finditer(normalized_text):
            line = str(match.group(1)).upper()
            batch_id = self._normalize_dash(str(match.group(2))).upper().strip()
            fields: dict[str, Any] = {}
            for key, value in params_regex.findall(normalized_text):
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

    def _parse_feeding(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("feeding", True):
            return []

        normalized_text = self._normalize_dash(text)
        batch_regex = re.compile(
            r"批次(?:号)?\s*[:：]?\s*"
            r"(S\d+(?:-[A-Z]{2})?-D[AB]\d{4}-\d+(?:-?[AB]\d)?)",
            re.IGNORECASE,
        )
        value_regexes: list[tuple[str, re.Pattern[str]]] = [
            ("磷酸铁需补(kg)", re.compile(r"磷酸铁需补\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("碳酸锂需补(kg)", re.compile(r"碳酸锂需补\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("D5总量(kg)", re.compile(r"D5(?:总量)?\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
            ("BL总量(kg)", re.compile(r"BL(?:总量)?\s*[:：]?\s*(\d+\.?\d*)\s*(?:kg)?", re.IGNORECASE)),
        ]

        extracted_values: dict[str, Any] = {}
        for field, pattern in value_regexes:
            match = pattern.search(normalized_text)
            if match:
                try:
                    extracted_values[field] = float(match.group(1))
                except Exception:
                    extracted_values[field] = match.group(1)

        if not extracted_values:
            return []

        records: list[ParsedRecord] = []
        for match in batch_regex.finditer(normalized_text):
            batch_id = self._normalize_dash(str(match.group(1))).upper().strip()
            line = "A" if "-DA" in batch_id else "B" if "-DB" in batch_id else "UNKNOWN"
            fields = dict(extracted_values)
            fields["消息时间"] = message_time
            route_key = f"feeding.{line}" if line in {"A", "B"} else "feeding"
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

    def _parse_sintering(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("sintering", True):
            return []

        normalized_text = self._normalize_dash(text)
        regex = re.compile(
            r"(S\d+-SC-[A-Z]{2}\d{4}-\d+)-([AB]\d+-\d+)-\d+\s*min\s*[:：]\s*([\d\.]+)",
            re.IGNORECASE,
        )

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for match in regex.finditer(normalized_text):
            base_id, sample_id, value = match.groups()
            base_id = base_id.upper().strip()
            sample_id = sample_id.upper().strip()
            line = "A" if sample_id.startswith("A") else "B" if sample_id.startswith("B") else "UNKNOWN"
            if line not in {"A", "B"}:
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
                    route_key=f"sintering.{line}",
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

    def _parse_crushing(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("crushing", True):
            return []

        normalized_text = self._normalize_dash(text)
        regex = re.compile(r"(S\d+-FS-[A-Z]{2}\d{4}-\d+)-([AB]\d-[^：:\n]+)[：:]\s*([\d\.]+)", re.IGNORECASE)

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for match in regex.finditer(normalized_text):
            base_id, sample_id, value = match.groups()
            base_id = base_id.upper().strip()
            sample_id = sample_id.upper().strip()
            sample_key, freq = self._split_sample_id(sample_id)

            if "-DA" in base_id:
                line = "A"
            elif "-DB" in base_id:
                line = "B"
            elif sample_key.startswith("A"):
                line = "A"
            elif sample_key.startswith("B"):
                line = "B"
            else:
                line = "UNKNOWN"

            if line not in {"A", "B"}:
                continue

            key = (base_id, line)
            if key not in grouped:
                grouped[key] = {"消息时间": message_time}

            grouped[key][sample_key] = float(value)
            if freq:
                grouped[key][f"{sample_key}_频率"] = freq

        records: list[ParsedRecord] = []
        for (batch_id, line), fields in grouped.items():
            records.append(
                ParsedRecord(
                    scenario="crushing",
                    line=line,
                    batch_id=batch_id,
                    route_key=f"crushing.{line}",
                    fields=fields,
                )
            )

        return records

    def _parse_pure_water(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("pure_water", True):
            return []

        normalized_text = self._normalize_dash(text)
        ph_match = re.search(r"车间[A/B]*线?纯水\s*PH\s*[:：]\s*(\d+\.?\d*)", normalized_text, re.IGNORECASE)
        if not ph_match:
            return []

        batch_regex = re.compile(r"(S\d+-TL-D[AB]\d{4}-\d+)", re.IGNORECASE)
        batch_matches = [self._normalize_dash(m.group(1)).upper().strip() for m in batch_regex.finditer(normalized_text)]
        if not batch_matches:
            return []

        batch_id = "\n".join(batch_matches)
        ph_value = float(ph_match.group(1))

        if all("-DA" in bid for bid in batch_matches):
            line = "A"
        elif all("-DB" in bid for bid in batch_matches):
            line = "B"
        else:
            line = "MIXED"

        route_key = f"pure_water.{line}" if line in {"A", "B"} else "pure_water"
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
    def _particle_process_name_map() -> dict[str, str]:
        return {
            "FS": "粉碎工序",
            "CM": "粗磨工序",
            "XM": "细磨工序",
            "HP": "合批工序",
            "QQT": "喷雾工序",
        }

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

    def _parse_particle_size(self, text: str, message_time: str) -> list[ParsedRecord]:
        if not self._process_switch("particle_size", True):
            return []

        normalized_text = self._normalize_dash(text)
        process_name_map = self._particle_process_name_map()
        # Support formats like:
        # S18-XM-DA2603-002
        # S18-XM-DA2603-002-C
        # S18-XM-DA2603-002-C-120min
        batch_regex = re.compile(
            r"(S\d+)-([A-Z]{2,3})-D([AB])(\d{4})-(\d+)"
            r"(?:-([A-Z0-9]+))?"
            r"(?:-(\d+)\s*MIN)?",
            re.IGNORECASE,
        )

        matches = list(batch_regex.finditer(normalized_text))
        if not matches:
            return []

        whole_d_values = self._extract_particle_d_values(normalized_text)
        records: list[ParsedRecord] = []

        for idx, match in enumerate(matches):
            material_type = str(match.group(1)).upper().strip()
            process_code = str(match.group(2)).upper().strip()
            line = str(match.group(3)).upper().strip()
            date_code = str(match.group(4)).strip()
            seq = str(match.group(5)).strip()
            sample_suffix = str(match.group(6) or "").upper().strip()
            hold_minutes = str(match.group(7) or "").strip()

            if process_code not in process_name_map:
                continue

            batch_id = f"{material_type}-{process_code}-D{line}{date_code}-{seq}"

            start_pos = match.start()
            end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized_text)
            block_text = normalized_text[start_pos:end_pos]
            d_values = self._extract_particle_d_values(block_text)
            if not d_values and len(matches) == 1:
                d_values = dict(whole_d_values)
            if not d_values:
                continue

            fields: dict[str, Any] = {
                "物料类型": material_type,
                "工序代码": process_code,
                "工序名称": process_name_map[process_code],
                "消息时间": message_time,
            }
            if sample_suffix:
                fields["样品段"] = sample_suffix
            if hold_minutes:
                try:
                    fields["保温(min)"] = int(hold_minutes)
                except Exception:
                    fields["保温(min)"] = hold_minutes
            fields.update(d_values)

            records.append(
                ParsedRecord(
                    scenario="particle_size",
                    line=line,
                    batch_id=batch_id,
                    route_key=f"particle_size.{process_code}",
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
        explicit_table_id = self._resolve_table_id(route_key)
        if explicit_table_id:
            return explicit_table_id

        cached = self._route_table_cache.get(route_key, "")
        if cached:
            return cached

        if not self._get_bool_config("auto_create_table_by_route", True):
            return ""

        table_name = self._resolve_table_name(route_key)
        table_id = await self._get_or_create_table_id_by_name(table_name)
        if table_id:
            self._route_table_cache[route_key] = table_id
            return table_id

        return self._get_str_config("bitable_default_table_id", "")

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

    def _parse_records(self, full_text: str, message_time: str) -> list[ParsedRecord]:
        records: list[ParsedRecord] = []
        records.extend(self._parse_particle_size(full_text, message_time))
        records.extend(self._parse_spray(full_text, message_time))
        records.extend(self._parse_feeding(full_text, message_time))
        records.extend(self._parse_sintering(full_text, message_time))
        records.extend(self._parse_crushing(full_text, message_time))
        records.extend(self._parse_pure_water(full_text, message_time))
        return records

    async def _handle_normal_message(self, event_ctx: context.EventContext) -> None:
        if self._mark_query_processed(event_ctx):
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
        records = self._parse_records(full_text, message_time)

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
            ok_fields, detail_fields, field_types = await self._ensure_table_fields(table_id, write_fields)
            if not ok_fields:
                errors.append(f"route={record.route_key}, {detail_fields}")
                continue
            normalized_write_fields = self._normalize_write_fields(write_fields, field_types)

            ok, detail = await self._write_record_to_bitable(table_id, normalized_write_fields)
            if ok:
                success_count += 1
                success_records.append(record)
            else:
                errors.append(f"route={record.route_key}, {detail}")

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


