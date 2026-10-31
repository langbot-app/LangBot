"""Dify Service API client for Runner.

This module provides a minimal Dify API client that doesn't depend on LangBot internals.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import typing

import httpx
from pkg.deadline import deadline
from pkg.endpoint import endpoint
from pkg.http_limits import limited_body, limited_bytes, limited_lines, limited_post

logger = logging.getLogger(__name__)


class DifyAPIError(Exception):
    """Dify API error."""

    def __init__(self, message: str, code: str = "dify.api_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class DifyConfigError(Exception):
    """Dify configuration error."""

    def __init__(self, message: str, code: str = "dify.config_invalid"):
        self.message = message
        self.code = code
        super().__init__(message)


async def _iter_sse_json(response):
    async for line in limited_lines(response, DifyAPIError):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except ValueError:
            raise DifyAPIError("Dify SSE data is not valid JSON", code="dify.response_invalid") from None
        if not isinstance(payload, dict):
            raise DifyAPIError("Dify SSE event is not a JSON object", code="dify.response_invalid")
        yield payload


class AsyncDifyClient:
    """Minimal Dify Service API client for Runner.

    Supports:
    - chat-messages (for chat and agent app types)
    - workflows/run (for workflow app type)
    - file upload (for multimodal input)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.dify.ai/v1",
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.base_url = endpoint(base_url).rstrip("/")
        self.timeout = timeout

    @deadline
    async def chat_messages(
        self,
        inputs: dict[str, typing.Any],
        query: str,
        user: str,
        conversation_id: str = "",
        files: list[dict[str, typing.Any]] = None,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Send chat message with streaming response.

        Yields SSE events as dicts.
        """
        files = files or []

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            trust_env=False,
        ) as client:
            payload = {
                "inputs": inputs,
                "query": query,
                "user": user,
                "response_mode": "streaming",
                "conversation_id": conversation_id,
                "files": files,
            }

            try:
                async with client.stream(
                    "POST",
                    "/chat-messages",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        error_body = await limited_body(response, DifyAPIError)
                        error_text = error_body.decode("utf-8", errors="replace")
                        raise DifyAPIError(
                            f"Dify API error: {response.status_code} - {error_text[:200]}",
                            code="dify.http_error",
                        )

                    async for event in _iter_sse_json(response):
                        yield event
            except httpx.TimeoutException:
                raise DifyAPIError(
                    f"Dify API request timed out after {self.timeout}s",
                    code="dify.timeout",
                ) from None
            except httpx.HTTPStatusError as e:
                raise DifyAPIError(
                    f"Dify HTTP error: {e.response.status_code}",
                    code="dify.http_error",
                ) from None

    @deadline
    async def workflow_run(
        self,
        inputs: dict[str, typing.Any],
        user: str,
        files: list[dict[str, typing.Any]] = None,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Run workflow with streaming response.

        Yields SSE events as dicts.
        """
        files = files or []

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            trust_env=False,
        ) as client:
            payload = {
                "inputs": inputs,
                "user": user,
                "response_mode": "streaming",
                "files": files,
            }

            try:
                async with client.stream(
                    "POST",
                    "/workflows/run",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        error_body = await limited_body(response, DifyAPIError)
                        error_text = error_body.decode("utf-8", errors="replace")
                        raise DifyAPIError(
                            f"Dify API error: {response.status_code} - {error_text[:200]}",
                            code="dify.http_error",
                        )

                    async for event in _iter_sse_json(response):
                        yield event
            except httpx.TimeoutException:
                raise DifyAPIError(
                    f"Dify API request timed out after {self.timeout}s",
                    code="dify.timeout",
                ) from None
            except httpx.HTTPStatusError as e:
                raise DifyAPIError(
                    f"Dify HTTP error: {e.response.status_code}",
                    code="dify.http_error",
                ) from None

    @deadline
    async def workflow_submit(
        self,
        form_token: str,
        workflow_run_id: str,
        inputs: dict[str, typing.Any],
        user: str,
        action: str = "",
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Submit human input and stream the resumed workflow events."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                trust_env=False,
            ) as client:
                response = await limited_post(
                    client,
                    f"/form/human_input/{form_token}",
                    DifyAPIError,
                    headers=headers,
                    json={"inputs": inputs, "user": user, "action": action},
                )
                if not response.is_success:
                    raise DifyAPIError(
                        f"Dify API error: {response.status_code} - {response.text[:200]}",
                        code="dify.http_error",
                    )

                async with client.stream(
                    "GET",
                    f"/workflow/{workflow_run_id}/events",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params={"user": user},
                ) as event_response:
                    if not event_response.is_success:
                        body = await limited_body(event_response, DifyAPIError)
                        raise DifyAPIError(
                            f"Dify API error: {event_response.status_code} - "
                            f"{body.decode('utf-8', errors='replace')[:200]}",
                            code="dify.http_error",
                        )
                    async for event in _iter_sse_json(event_response):
                        yield event
        except httpx.TimeoutException:
            raise DifyAPIError(
                f"Dify API request timed out after {self.timeout}s",
                code="dify.timeout",
            ) from None

    @deadline
    async def download_file(self, url: str) -> tuple[bytes, str]:
        """Stage an explicitly supplied HTTP file URL, never a local path."""
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise DifyAPIError("Input file URL must use HTTP or HTTPS", code="dify.input_error")
        endpoint(url, query=True)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False, follow_redirects=False) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in limited_bytes(response, DifyAPIError):
                        body.extend(chunk)
                        if len(body) > 10 * 1024 * 1024:
                            raise DifyAPIError("Dify input file exceeds the size limit", code="dify.input_error")
                    mime = (
                        response.headers.get("content-type")
                        or mimetypes.guess_type(url)[0]
                        or "application/octet-stream"
                    )
                    return bytes(body), mime
        except httpx.HTTPError:
            # URLs and transport exception details may contain signed credentials.
            raise DifyAPIError("Dify input file download failed", code="dify.input_error") from None

    @deadline
    async def upload_file(
        self,
        file_name: str,
        file_bytes: bytes,
        content_type: str,
        user: str,
    ) -> dict[str, typing.Any]:
        """Upload file to Dify and return file info with id."""
        if len(file_bytes) > 10 * 1024 * 1024:
            raise DifyAPIError("Dify upload exceeds the size limit", code="dify.input_error")
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            trust_env=False,
        ) as client:
            files = {"file": (file_name, file_bytes, content_type)}
            data = {"user": user}

            try:
                response = await limited_post(
                    client,
                    "/files/upload",
                    DifyAPIError,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files=files,
                    data=data,
                )

                if response.status_code not in (200, 201):
                    error_text = response.text[:200]
                    raise DifyAPIError(
                        f"Dify file upload failed: {response.status_code} - {error_text}",
                        code="dify.http_error",
                    )

                try:
                    payload = response.json()
                except (ValueError, UnicodeDecodeError):
                    raise DifyAPIError("Dify upload response is not valid JSON", code="dify.response_invalid") from None
                if isinstance(payload, dict):
                    payload = payload.get("data", payload)
                if not isinstance(payload, dict) or not isinstance(payload.get("id"), str) or not payload["id"]:
                    raise DifyAPIError("Dify upload response has no valid file id", code="dify.response_invalid")
                return payload
            except httpx.TimeoutException:
                raise DifyAPIError(
                    f"Dify file upload timed out after {self.timeout}s",
                    code="dify.timeout",
                ) from None


def extract_text_from_output(value: typing.Any) -> str:
    """Extract text content from Dify output payload."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        # Try to parse as JSON to extract content field
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and isinstance(parsed.get("content"), str):
                return parsed["content"]
        except json.JSONDecodeError:
            pass
        return value
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, str):
            return content
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def process_thinking_content(content: str, remove_think: bool = False) -> tuple[str, str]:
    """Process thinking content (reasoning tags) in Dify responses.

    Args:
        content: Original content
        remove_think: Whether to remove thinking tags

    Returns:
        (processed_content, thinking_content)
    """
    import re

    thinking_content = ""
    if content and "<think>" in content and "</think>" in content:
        think_pattern = r"<think>(.*?)</think>"
        think_matches = re.findall(think_pattern, content, re.DOTALL)
        if think_matches:
            thinking_content = "\n".join(think_matches)
            content = re.sub(think_pattern, "", content, flags=re.DOTALL).strip()

    if remove_think:
        # Never expose an unfinished reasoning block while streaming or pausing.
        if "<think>" in content:
            content = content.split("<think>", 1)[0].rstrip()
        return content, ""
    else:
        if thinking_content:
            content = f"<think>\n{thinking_content}\n</think>\n{content}".strip()
        return content, thinking_content
