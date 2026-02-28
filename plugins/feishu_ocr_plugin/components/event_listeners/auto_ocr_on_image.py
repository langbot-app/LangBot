from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path
from typing import Any

import httpx

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


class AutoOcrOnImageListener(EventListener):
    def __init__(self):
        super().__init__()
        self._tenant_access_token: str = ""
        self._tenant_access_token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(events.PersonNormalMessageReceived)
        async def _on_person_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_normal_message(event_ctx)

        @self.handler(events.GroupNormalMessageReceived)
        async def _on_group_normal_message(event_ctx: context.EventContext) -> None:
            await self._handle_normal_message(event_ctx)

    def _get_timeout_seconds(self) -> float:
        raw = str(self.plugin.get_config().get("timeout_seconds", "20")).strip()
        try:
            timeout = float(raw)
        except ValueError:
            timeout = 20.0
        return max(1.0, min(120.0, timeout))

    @staticmethod
    def _strip_data_url_prefix(data: str) -> str:
        if data.startswith("data:") and "," in data:
            return data.split(",", 1)[1]
        return data

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
                    raise ValueError(
                        f"Failed to download image from url, HTTP {response.status_code}."
                    )
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
            cfg.get(
                "token_endpoint",
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            )
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
            raise RuntimeError(
                f"Token endpoint failed, code={code}, msg={body.get('msg', '')}"
            )

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

    async def _recognize_image_bytes(self, image_bytes: bytes) -> dict[str, Any]:
        cfg = self.plugin.get_config()
        ocr_endpoint = str(
            cfg.get(
                "ocr_endpoint",
                "https://open.feishu.cn/open-apis/optical_char_recognition/v1/image/basic_recognize",
            )
        ).strip()

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
            return {
                "success": False,
                "error": f"OCR request failed, HTTP {response.status_code}.",
                "response_text": response.text[:500],
            }

        try:
            body = response.json()
        except Exception:
            return {
                "success": False,
                "error": "OCR response is not JSON.",
                "response_text": response.text[:500],
            }

        code = int(body.get("code", 0))
        if code != 0:
            return {
                "success": False,
                "error": "OCR endpoint returned error.",
                "code": code,
                "msg": body.get("msg", ""),
                "log_id": body.get("log_id", ""),
            }

        data = body.get("data", {}) or {}
        text_list = data.get("text_list", []) or []
        lines: list[str] = []
        for item in text_list:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    lines.append(text)
            elif isinstance(item, str) and item.strip():
                lines.append(item)

        return {
            "success": True,
            "text": "\n".join(lines).strip(),
            "text_list": text_list,
        }

    @staticmethod
    def _format_result_text(result: dict[str, Any]) -> str:
        if not result.get("success"):
            error = str(result.get("error", "Unknown OCR error")).strip()
            msg = str(result.get("msg", "")).strip()
            if msg:
                return f"OCR failed: {error} ({msg})"
            return f"OCR failed: {error}"

        text = str(result.get("text", "")).strip()
        if not text:
            return "OCR completed, but no text was recognized."

        if len(text) > 3000:
            return f"{text[:3000]}\n...[truncated]"
        return text

    def _build_reply_text(self, result_list: list[dict[str, Any]]) -> str:
        if not result_list:
            return "No image was found for OCR."

        if len(result_list) == 1:
            formatted = self._format_result_text(result_list[0])
            if result_list[0].get("success"):
                return f"OCR result:\n{formatted}"
            return formatted

        parts: list[str] = []
        for idx, result in enumerate(result_list, start=1):
            formatted = self._format_result_text(result)
            parts.append(f"Image {idx}:\n{formatted}")
        return "\n\n".join(parts)

    async def _handle_normal_message(self, event_ctx: context.EventContext) -> None:
        message_chain = event_ctx.event.message_chain
        images = [component for component in message_chain if isinstance(component, platform_message.Image)]

        if not images:
            return

        result_list: list[dict[str, Any]] = []
        for image in images:
            try:
                image_bytes = await self._get_image_bytes(image)
                result = await self._recognize_image_bytes(image_bytes)
            except Exception as exc:
                result = {
                    "success": False,
                    "error": str(exc),
                }
            result_list.append(result)

        reply_text = self._build_reply_text(result_list)
        event_ctx.event.reply_message_chain = platform_message.MessageChain(
            [platform_message.Plain(text=reply_text)]
        )
        event_ctx.prevent_default()
        event_ctx.prevent_postorder()
