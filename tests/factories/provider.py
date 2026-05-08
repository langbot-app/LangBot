"""
Fake provider factory for tests.

Provides a deterministic fake provider that simulates LLM responses without real API calls.
"""

from __future__ import annotations

from unittest.mock import Mock
import typing

import langbot_plugin.api.entities.builtin.provider.message as provider_message


class FakeProvider:
    """Deterministic fake provider for unit and integration tests.

    Simulates various provider behaviors:
    - Normal text response
    - Streaming response
    - Timeout error
    - Auth error
    - Rate-limit error
    - Malformed response

    Does not call real LLM vendors.
    Does not require API keys.
    """

    PONG_RESPONSE = "LANGBOT_FAKE_PONG"

    def __init__(
        self,
        *,
        default_response: str = "fake response",
        streaming_chunks: list[str] = None,
        raise_error: Exception = None,
        captured_requests: list = None,
    ):
        self._default_response = default_response
        self._streaming_chunks = streaming_chunks or ["fake ", "response"]
        self._raise_error = raise_error
        self._captured_requests = captured_requests if captured_requests is not None else []

    def returns(self, text: str) -> "FakeProvider":
        """Configure provider to return a specific text response."""
        self._default_response = text
        self._streaming_chunks = [text]
        return self

    def returns_streaming(self, chunks: list[str]) -> "FakeProvider":
        """Configure provider to return streaming chunks."""
        self._streaming_chunks = chunks
        self._default_response = "".join(chunks)
        return self

    def raises(self, error: Exception) -> "FakeProvider":
        """Configure provider to raise an error."""
        self._raise_error = error
        return self

    def timeout(self) -> "FakeProvider":
        """Configure provider to simulate timeout."""
        return self.raises(TimeoutError("Provider timeout"))

    def auth_error(self) -> "FakeProvider":
        """Configure provider to simulate auth error."""
        return self.raises(Exception("Invalid API key"))

    def rate_limit(self) -> "FakeProvider":
        """Configure provider to simulate rate limit."""
        return self.raises(Exception("Rate limit exceeded"))

    def malformed(self) -> "FakeProvider":
        """Configure provider to simulate malformed response."""
        self._default_response = None
        return self

    def get_captured_requests(self) -> list:
        """Get all captured request arguments for assertions."""
        return self._captured_requests.copy()

    def clear_captured_requests(self):
        """Clear captured requests."""
        self._captured_requests.clear()

    def _create_message(self, content: str) -> provider_message.Message:
        """Create a provider message from text content."""
        return provider_message.Message(
            role="assistant",
            content=content,
        )

    def _create_chunk(
        self,
        content: str,
        is_final: bool = False,
        msg_sequence: int = 0,
    ) -> provider_message.MessageChunk:
        """Create a provider message chunk."""
        return provider_message.MessageChunk(
            role="assistant",
            content=content,
            is_final=is_final,
            msg_sequence=msg_sequence,
        )

    async def invoke_llm(
        self,
        query,
        model,
        messages: list,
        funcs: list,
        extra_args: dict,
        remove_think: bool = False,
    ) -> provider_message.Message:
        """Simulate non-streaming LLM invocation."""
        # Capture request for assertions
        self._captured_requests.append({
            "query_id": query.query_id if query else None,
            "model": model.model_entity.name if model and hasattr(model, 'model_entity') else None,
            "messages": messages,
            "funcs": funcs,
            "extra_args": extra_args,
        })

        # Simulate error if configured
        if self._raise_error:
            raise self._raise_error

        # Return response
        if self._default_response is None:
            # Malformed response
            return provider_message.Message(role="assistant", content=None)

        return self._create_message(self._default_response)

    async def invoke_llm_stream(
        self,
        query,
        model,
        messages: list,
        funcs: list,
        extra_args: dict,
        remove_think: bool = False,
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """Simulate streaming LLM invocation."""
        # Capture request for assertions
        self._captured_requests.append({
            "query_id": query.query_id if query else None,
            "model": model.model_entity.name if model and hasattr(model, 'model_entity') else None,
            "messages": messages,
            "funcs": funcs,
            "extra_args": extra_args,
            "streaming": True,
        })

        # Simulate error if configured
        if self._raise_error:
            raise self._raise_error

        # Yield chunks
        for i, chunk in enumerate(self._streaming_chunks):
            is_final = (i == len(self._streaming_chunks) - 1)
            yield self._create_chunk(chunk, is_final=is_final, msg_sequence=i)


def fake_provider(
    default_response: str = "fake response",
) -> FakeProvider:
    """Create a FakeProvider with optional default response."""
    return FakeProvider(default_response=default_response)


def fake_provider_pong() -> FakeProvider:
    """Create a FakeProvider that returns the pong response."""
    return FakeProvider(default_response=FakeProvider.PONG_RESPONSE)


def fake_provider_timeout() -> FakeProvider:
    """Create a FakeProvider that simulates timeout."""
    return FakeProvider().timeout()


def fake_provider_auth_error() -> FakeProvider:
    """Create a FakeProvider that simulates auth error."""
    return FakeProvider().auth_error()


def fake_provider_rate_limit() -> FakeProvider:
    """Create a FakeProvider that simulates rate limit."""
    return FakeProvider().rate_limit()


def fake_provider_malformed() -> FakeProvider:
    """Create a FakeProvider that simulates malformed response."""
    return FakeProvider().malformed()


# ============== Mock Model Factory ==============


def fake_model(
    *,
    uuid: str = "test-model-uuid",
    name: str = "test-model",
    abilities: list[str] = None,
    provider: FakeProvider = None,
) -> Mock:
    """Create a mock model with a fake provider."""
    model = Mock()
    model.model_entity = Mock()
    model.model_entity.uuid = uuid
    model.model_entity.name = name
    model.model_entity.abilities = abilities or ["func_call", "vision"]
    model.model_entity.extra_args = {}

    # Attach fake provider
    if provider is None:
        provider = FakeProvider()

    model.provider = provider

    return model