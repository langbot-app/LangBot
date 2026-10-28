"""Index strategy registry and factory."""

import logging

from .base import IndexStrategy
from .chunk import ChunkStrategy
from .parent_child import ParentChildStrategy
from .qa import QAStrategy

logger = logging.getLogger(__name__)

_STRATEGIES: dict[str, type[IndexStrategy]] = {
    "chunk": ChunkStrategy,
    "parent_child": ParentChildStrategy,
    "qa": QAStrategy,
}


def get_strategy(index_type: str) -> IndexStrategy:
    """Return an IndexStrategy instance for the given *index_type*.

    Falls back to :class:`ChunkStrategy` for unknown values.
    """
    cls = _STRATEGIES.get(index_type)
    if cls is None:
        logger.warning(
            f"Unknown index_type '{index_type}', falling back to 'chunk' strategy"
        )
        cls = ChunkStrategy
    return cls()
