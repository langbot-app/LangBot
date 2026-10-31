"""Langflow API client for Runner.

This module provides a minimal Langflow API client that doesn't depend on LangBot internals.
"""

from __future__ import annotations

import json
import logging
import typing
import uuid

import httpx

from pkg.deadline import deadline
from pkg.endpoint import endpoint
from pkg.http_limits import limited_body, limited_lines, limited_post

logger = logging.getLogger(__name__)


class LangflowAPIError(Exception):
    """Langflow API error."""

    def __init__(self, message: str, code: str = "langflow.api_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class LangflowConfigError(Exception):
    """Langflow configuration error."""

    def __init__(self, message: str, code: str = "langflow.config_invalid"):
        self.message = message
        self.code = code
        super().__init__(message)


class AsyncLangflowClient:
    """Minimal Langflow API client for Runner.

    Supports:
    - /api/v1/run/{flow_id} endpoint for flow execution
    - Streaming (SSE) and non-streaming responses
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:7860",
        timeout: float = 120.0,
    ):
        self.api_key = api_key
        self.base_url = endpoint(base_url).rstrip("/")
        self.timeout = timeout

    def _get_headers(self) -> dict[str, str]:
        """Get common request headers."""
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }

    def _build_payload(
        self,
        input_value: str,
        input_type: str = "chat",
        output_type: str = "chat",
        tweaks: dict[str, typing.Any] = None,
        session_id: str = None,
    ) -> dict[str, typing.Any]:
        """Build request payload for Langflow API."""
        payload = {
            "output_type": output_type,
            "input_type": input_type,
            "input_value": input_value,
        }

        if session_id:
            payload["session_id"] = session_id
        else:
            payload["session_id"] = str(uuid.uuid4())

        if tweaks:
            payload["tweaks"] = tweaks

        return payload

    @deadline
    async def run_flow(
        self,
        flow_id: str,
        input_value: str,
        input_type: str = "chat",
        output_type: str = "chat",
        tweaks: dict[str, typing.Any] = None,
        session_id: str = None,
        stream: bool = True,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Run a Langflow flow.

        Yields SSE events as dicts when streaming, or a single result dict when not streaming.

        Args:
            flow_id: The Langflow flow ID
            input_value: The input text to send to the flow
            input_type: Input type (default: "chat")
            output_type: Output type (default: "chat")
            tweaks: Optional tweaks configuration
            session_id: Optional session ID for stateful sessions
            stream: Whether to use streaming mode

        Yields:
            Parsed event data as dict
        """
        url = f"{self.base_url}/api/v1/run/{flow_id}"
        payload = self._build_payload(
            input_value=input_value,
            input_type=input_type,
            output_type=output_type,
            tweaks=tweaks,
            session_id=session_id,
        )

        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            try:
                if stream:
                    async with client.stream(
                        "POST",
                        url,
                        headers=self._get_headers(),
                        json=payload,
                    ) as response:
                        if response.status_code != 200:
                            error_body = await limited_body(response, LangflowAPIError)
                            error_text = error_body.decode("utf-8", errors="replace")
                            raise LangflowAPIError(
                                f"Langflow API error: {response.status_code} - {error_text[:200]}",
                                code="langflow.http_error",
                            )

                        async for line in limited_lines(response, LangflowAPIError):
                            if not line or not line.strip():
                                continue

                            data_str = line
                            if data_str.startswith("data: "):
                                data_str = data_str[6:]  # Remove "data: " prefix

                            if not data_str.strip():
                                continue

                            try:
                                yield json.loads(data_str)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse Langflow SSE data: {e}")
                                # Skip malformed lines instead of failing
                                continue
                else:
                    # Non-streaming mode
                    response = await limited_post(
                        client,
                        url,
                        LangflowAPIError,
                        headers=self._get_headers(),
                        json=payload,
                    )

                    if response.status_code != 200:
                        error_text = response.text[:200]
                        raise LangflowAPIError(
                            f"Langflow API error: {response.status_code} - {error_text}",
                            code="langflow.http_error",
                        )

                    yield response.json()

            except httpx.TimeoutException:
                raise LangflowAPIError(
                    f"Langflow API request timed out after {self.timeout}s",
                    code="langflow.timeout",
                ) from None
            except httpx.HTTPStatusError as e:
                raise LangflowAPIError(
                    f"Langflow HTTP error: {e.response.status_code}",
                    code="langflow.http_error",
                ) from None


def extract_message_from_response(response_data: dict[str, typing.Any]) -> str:
    """Extract message text from Langflow API response.

    Langflow response structure:
    - outputs[0].outputs[0].outputs.message.message (primary path)
    - messages[0].message (fallback path)

    Args:
        response_data: Parsed JSON response from Langflow API

    Returns:
        Extracted message text, or empty string if not found
    """
    message_text = ""

    # Primary path: outputs[0].outputs[0].outputs.message.message
    if "outputs" in response_data and len(response_data["outputs"]) > 0:
        output = response_data["outputs"][0]
        if isinstance(output, dict) and "outputs" in output and len(output["outputs"]) > 0:
            inner_output = output["outputs"][0]
            if isinstance(inner_output, dict):
                inner_outputs = inner_output.get("outputs", {})
                if isinstance(inner_outputs, dict) and "message" in inner_outputs:
                    message_data = inner_outputs["message"]
                    if isinstance(message_data, dict) and "message" in message_data:
                        message_text = message_data["message"]

    # Fallback path: messages[0].message
    if not message_text and "messages" in response_data:
        messages = response_data["messages"]
        if messages and len(messages) > 0:
            message_text = messages[0].get("message", "")

    return message_text
