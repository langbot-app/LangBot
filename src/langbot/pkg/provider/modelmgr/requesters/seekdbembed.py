from __future__ import annotations

import typing

from .. import requester

REQUESTER_NAME: str = 'seekdb-embedding'


class SeekDBEmbedding(requester.ProviderAPIRequester):
    """SeekDB built-in embedding requester.

    Uses pyseekdb's local embedding function (all-MiniLM-L6-v2).
    The base_url config is reserved for future remote embedding support.
    """

    default_config: dict[str, typing.Any] = {
        'base_url': '',
    }

    _embedding_function = None

    async def initialize(self):
        try:
            import pyseekdb
        except ImportError:
            raise ImportError('pyseekdb is not installed. Install it with: pip install pyseekdb')

        self._embedding_function = pyseekdb.get_default_embedding_function()

    async def invoke_llm(
        self,
        query,
        model: requester.RuntimeLLMModel,
        messages: typing.List,
        funcs: typing.List = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ):
        raise NotImplementedError('SeekDB embedding does not support LLM inference')

    async def invoke_embedding(
        self,
        model: requester.RuntimeEmbeddingModel,
        input_text: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> typing.List[typing.List[float]]:
        """Generate embeddings using SeekDB's built-in embedding function."""
        try:
            if self._embedding_function is None:
                await self.initialize()

            if self._embedding_function is None:
                raise RuntimeError('SeekDB embedding function initialization failed')

            return self._embedding_function(input_text)
        except Exception as e:
            from .. import errors

            raise errors.RequesterError(f'SeekDB embedding failed: {str(e)}')
