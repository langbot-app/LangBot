"""
RAG Reranker Manager.

This module provides the RerankerManager class for creating and managing reranker instances.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langbot.pkg.core import app
    from .providers.base import BaseReranker


class RerankerManager:
    """
    Manager class for creating and managing reranker instances.
    """

    @staticmethod
    def create_reranker(ap: "app.Application", config: dict = None) -> "BaseReranker":
        """
        Factory method to create reranker instances based on configuration.

        Args:
            ap: Application instance
            config: Reranker configuration

        Returns:
            Configured reranker instance
        """
        config = config or {}
        reranker_type = config.get('type', 'simple')

        if reranker_type == 'qwen':
            from .providers.qwen import QwenReranker
            return QwenReranker(ap, config)
        else:
            # Default to simple reranker
            from .providers.simple import SimpleReranker
            return SimpleReranker(ap, config)
