from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session


class FeishuOcrImageTool(Tool):
    def __init__(self):
        super().__init__()
        self._tenant_access_token: str = ""
        self._tenant_access_token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

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

    async def _get_image_bytes(self, params: dict[str, Any]) -> bytes:
        image_url = str(params.get("image_url", "")).strip()
        image_base64 = str(params.get("image_base64", "")).strip()

        if not image_url and not image_base64:
            raise ValueError("Either image_url or image_base64 is required.")

        if image_base64:
            try:
                normalized = self._strip_data_url_prefix(image_base64)
                return base64.b64decode(normalized)
            except Exception as exc:
                raise ValueError(f"Invalid image_base64: {exc}") from exc

        timeout = self._get_timeout_seconds()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(image_url)
            if response.status_code != 200:
                raise ValueError(
                    f"Failed to download image from image_url, HTTP {response.status_code}."
                )
            return response.content

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
        # Reserve 5 minutes as safety buffer.
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

    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> dict[str, Any]:
        _ = session
        _ = query_id

        cfg = self.plugin.get_config()
        ocr_endpoint = str(
            cfg.get(
                "ocr_endpoint",
                "https://open.feishu.cn/open-apis/optical_char_recognition/v1/image/basic_recognize",
            )
        ).strip()

        try:
            image_bytes = await self._get_image_bytes(params)
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
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
            }
