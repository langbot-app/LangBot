from __future__ import annotations

import json
from typing import Any

import httpx


SYSTEM_PROMPT = """你是磷酸铁锂制程、成品和配方复盘分析助手。
只能基于输入证据分析，不得编造未提供的数据。
必须区分事实、判断、建议和待确认项。
不得给出自动放行、报废、降级、改配方的最终决策。
涉及配方、原料或工艺调整时，只能给出验证建议和风险提示。
输出使用中文，结构清晰，适合发送到生产/质量/工艺协作群。"""


class LlmClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        temperature: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = max(5.0, min(float(timeout_seconds), 180.0))
        self.temperature = max(0.0, min(float(temperature), 1.0))

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    async def complete_report(self, payload: dict[str, Any]) -> str:
        if not self.enabled:
            raise RuntimeError("AI 未配置。")

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "请基于以下 JSON 证据生成分析报告：\n"
                    + json.dumps(payload, ensure_ascii=False, default=str),
                },
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json=body)
        if response.status_code >= 400:
            raise RuntimeError(f"AI HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("AI 返回为空。")
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = str(message.get("content", "")).strip()
        if not content:
            raise RuntimeError("AI 内容为空。")
        return content

