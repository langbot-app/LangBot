from __future__ import annotations

import typing

from .. import requester

REQUESTER_NAME: str = 'chroma-embedding'


class ChromaEmbedding(requester.ProviderAPIRequester):
    """Chroma built-in embedding requester.

    Uses chromadb's DefaultEmbeddingFunction (all-MiniLM-L6-v2).
    The embedding function runs locally using ONNX Runtime.
    """

    default_config: dict[str, typing.Any] = {
        'base_url': '',
    }

    _embedding_function = None

    async def initialize(self):
        try:
            from chromadb.utils import embedding_functions
        except ImportError:
            raise ImportError('chromadb is not installed. Install it with: pip install chromadb')

        self._embedding_function = embedding_functions.DefaultEmbeddingFunction()

    async def invoke_llm(
        self,
        query,
        model: requester.RuntimeLLMModel,
        messages: typing.List,
        funcs: typing.List = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ):
        raise NotImplementedError('Chroma embedding does not support LLM inference')

    async def invoke_embedding(
        self,
        model: requester.RuntimeEmbeddingModel,
        input_text: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> typing.List[typing.List[float]]:
        """Generate embeddings using Chroma's DefaultEmbeddingFunction."""
        if self._embedding_function is None:
            await self.initialize()

        try:
            result = self._embedding_function(input_text)
            # DefaultEmbeddingFunction returns list of ndarray, convert for JSON
            if isinstance(result, list):
                return [item.tolist() if hasattr(item, 'tolist') else item for item in result]
            return result.tolist() if hasattr(result, 'tolist') else result
        except Exception as e:
            from .. import errors

            raise errors.RequesterError(f'Chroma embedding failed: {str(e)}')
