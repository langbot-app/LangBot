from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from components.analysis_service import AnalysisService
from components.command_parser import parse_analysis_command
from components.data_sources import FeishuBaseSource, FeishuSheetSource
from components.llm_client import LlmClient


class AiAnalysisListener(EventListener):
    def __init__(self) -> None:
        super().__init__()
        self._tenant_access_token = ""
        self._tenant_access_token_expire_at = 0.0
        self._token_lock = asyncio.Lock()
        self._base_source = FeishuBaseSource(self._call_feishu_json_api)
        self._sheet_source = FeishuSheetSource(self._call_feishu_json_api)

    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def _on_person_message(event_ctx: context.EventContext) -> None:
            await self._handle_message(event_ctx)

        @self.handler(events.GroupMessageReceived)
        async def _on_group_message(event_ctx: context.EventContext) -> None:
            await self._handle_message(event_ctx)

        @self.handler(events.PersonNormalMessageReceived)
        async def _on_person_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_message(event_ctx)

        @self.handler(events.GroupNormalMessageReceived)
        async def _on_group_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_message(event_ctx)

    def _get_config(self, key: str, default: Any = "") -> Any:
        return self.plugin.get_config().get(key, default)

    def _get_str_config(self, key: str, default: str = "") -> str:
        return str(self._get_config(key, default)).strip()

    def _get_bool_config(self, key: str, default: bool) -> bool:
        value = self._get_config(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _get_int_config(self, key: str, default: int, min_value: int, max_value: int) -> int:
        raw = self._get_config(key, default)
        try:
            value = int(str(raw).strip())
        except Exception:
            value = default
        return max(min_value, min(max_value, value))

    def _get_float_config(self, key: str, default: float, min_value: float, max_value: float) -> float:
        raw = self._get_config(key, default)
        try:
            value = float(str(raw).strip())
        except Exception:
            value = default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _split_csv(raw: str) -> list[str]:
        return [item.strip() for item in re.split(r"[,\n;，；]+", raw or "") if item.strip()]

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
        return str(getattr(event_ctx.event, "launcher_type", "")).strip().lower() == "group"

    @staticmethod
    def _is_person_event(event_ctx: context.EventContext) -> bool:
        return str(getattr(event_ctx.event, "launcher_type", "")).strip().lower() == "person"

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

    async def _reply_text(self, event_ctx: context.EventContext, text: str) -> None:
        if not text:
            return
        limit = self._get_int_config("reply_max_chars", 3500, 800, 10000)
        clipped = text if len(text) <= limit else text[: limit - 30] + "\n...（内容已截断）"
        chain = platform_message.MessageChain([platform_message.Plain(text=clipped)])
        if self._event_supports_reply_chain(event_ctx):
            event_ctx.event.reply_message_chain = chain
            return
        launcher_type = str(getattr(event_ctx.event, "launcher_type", "")).strip().lower()
        launcher_id = str(getattr(event_ctx.event, "launcher_id", "")).strip()
        bot_uuid = await self._resolve_bot_uuid(event_ctx)
        if launcher_type and launcher_id and bot_uuid:
            await self.plugin.send_message(
                bot_uuid=bot_uuid,
                target_type=launcher_type,
                target_id=launcher_id,
                message_chain=chain,
            )

    async def _request_tenant_access_token(self) -> str:
        app_id = self._get_str_config("app_id", "")
        app_secret = self._get_str_config("app_secret", "")
        if not app_id or not app_secret:
            raise ValueError("插件配置 app_id/app_secret 必填。")
        endpoint = self._get_str_config(
            "token_endpoint",
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        )
        async with httpx.AsyncClient(timeout=self._get_float_config("timeout_seconds", 30, 3, 180)) as client:
            response = await client.post(endpoint, json={"app_id": app_id, "app_secret": app_secret})
        if response.status_code != 200:
            raise RuntimeError(f"Token 获取失败，HTTP {response.status_code}: {response.text[:300]}")
        body = response.json()
        if int(body.get("code", 0)) != 0:
            raise RuntimeError(f"Token 获取失败，code={body.get('code')}，msg={body.get('msg', '')}")
        token = str(body.get("tenant_access_token", "")).strip()
        if not token:
            raise RuntimeError("tenant_access_token 为空。")
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

    async def _build_auth_headers(self) -> dict[str, str]:
        token = await self._get_tenant_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

    async def _call_feishu_json_api(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timeout = self._get_float_config("timeout_seconds", 30, 3, 180)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, endpoint, headers=headers, json=payload, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
        body = response.json()
        code = int(body.get("code", 0))
        if code != 0:
            raise RuntimeError(f"code={code}, msg={body.get('msg', '')}")
        data = body.get("data", {}) or {}
        return data if isinstance(data, dict) else {}

    async def _resolve_wiki_obj_token(self, token_or_url: str, expected_type: str, headers: dict[str, str]) -> str:
        raw = str(token_or_url or "").strip()
        if not raw:
            return ""
        parsed = urlparse(raw)
        path = parsed.path if parsed.scheme else ""
        if "/wiki/" not in path:
            return raw.rstrip("/").split("/")[-1].split("?")[0]
        wiki_token = path.rstrip("/").split("/")[-1]
        endpoint = "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node"
        data = await self._call_feishu_json_api("GET", endpoint, headers=headers, params={"token": wiki_token})
        node = data.get("node", {}) if isinstance(data.get("node"), dict) else {}
        obj_type = str(node.get("obj_type", "")).strip()
        obj_token = str(node.get("obj_token", "")).strip()
        if expected_type and obj_type and obj_type != expected_type:
            raise ValueError(f"链接类型为 {obj_type}，不是期望的 {expected_type}。")
        return obj_token

    def _build_llm_client(self) -> LlmClient | None:
        if not self._get_bool_config("enable_ai", True):
            return None
        return LlmClient(
            base_url=self._get_str_config("llm_base_url", ""),
            api_key=self._get_str_config("llm_api_key", ""),
            model=self._get_str_config("llm_model", ""),
            timeout_seconds=self._get_float_config("llm_timeout_seconds", 60, 5, 180),
            temperature=self._get_float_config("llm_temperature", 0.2, 0, 1),
        )

    async def _handle_message(self, event_ctx: context.EventContext) -> None:
        in_group = self._is_group_event(event_ctx)
        in_person = self._is_person_event(event_ctx)
        if in_group and not self._get_bool_config("reply_in_group", True):
            return
        if in_person and not self._get_bool_config("reply_in_person", True):
            return

        plain_text = self._extract_plain_text(event_ctx.event.message_chain)
        parsed = parse_analysis_command(
            plain_text,
            batch_commands=self._get_str_config("batch_commands", "批次分析,制程复盘"),
            abnormal_commands=self._get_str_config("abnormal_commands", "异常分析"),
            product_commands=self._get_str_config("product_commands", "成品分析,成品趋势,成品异常"),
            recipe_commands=self._get_str_config("recipe_commands", "配方复盘,配方建议"),
            similar_commands=self._get_str_config("similar_commands", "相似批次"),
        )
        if not parsed.triggered:
            return
        event_ctx.prevent_default()
        event_ctx.prevent_postorder()

        if parsed.error:
            await self._reply_text(event_ctx, parsed.error)
            return
        command = parsed.value
        if command is None:
            return

        try:
            headers = await self._build_auth_headers()
            process_base_token = await self._resolve_wiki_obj_token(
                self._get_str_config("process_base_token", ""),
                "bitable",
                headers,
            )
            product_sheet_token = await self._resolve_wiki_obj_token(
                self._get_str_config("product_spreadsheet_token", ""),
                "sheet",
                headers,
            )
            service = AnalysisService(
                base_source=self._base_source,
                sheet_source=self._sheet_source,
                llm_client=self._build_llm_client(),
            )

            product_patterns = self._split_csv(
                self._get_str_config("product_sheet_patterns", "成品数据源,S18,S006,S20")
            )
            if command.kind == "product":
                if not product_sheet_token:
                    raise ValueError("未配置 product_spreadsheet_token。")
                text = await service.analyze_product(
                    spreadsheet_token=product_sheet_token,
                    headers=headers,
                    target=command.target,
                    date_arg=command.date_arg,
                    sheet_patterns=product_patterns,
                    product_range=self._get_str_config("product_range", "A1:ZZ2000"),
                    max_rows=self._get_int_config("product_max_rows", 80, 5, 500),
                )
            else:
                if not process_base_token:
                    raise ValueError("未配置 process_base_token。")
                wide = await service.build_batch_wide_table(
                    app_token=process_base_token,
                    spreadsheet_token=product_sheet_token,
                    headers=headers,
                    batch_text=command.batch,
                    process_tables_raw=self._get_config("process_tables_json", ""),
                    product_sheet_patterns=product_patterns,
                    product_range=self._get_str_config("product_range", "A1:ZZ2000"),
                    batch_field=self._get_str_config("batch_field", "批次号"),
                    message_time_field=self._get_str_config("message_time_field", "消息时间"),
                    scan_limit=self._get_int_config("scan_limit", 500, 50, 5000),
                    max_stage_fields=self._get_int_config("max_stage_fields", 30, 8, 120),
                )
                mode = "abnormal" if command.kind == "abnormal" else ("recipe" if command.kind in {"recipe", "similar"} else "batch")
                abnormal = command.abnormal if command.kind == "abnormal" else ""
                text = await service.analyze_batch(wide, abnormal=abnormal, mode=mode)
            await self._reply_text(event_ctx, text)
        except Exception as exc:
            await self._reply_text(event_ctx, f"AI分析失败：{exc}")

