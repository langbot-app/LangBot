from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import List, Dict, Any

from langbot.pkg.core import app
from langbot_plugin.api.entities.builtin.rag import context as rag_context

from .providers.base import BaseRetrievalProvider
from .providers.vector import VectorSearchProvider
from .rerank.base import BaseReranker
from .rerank.simple import SimpleReranker


class Retriever:
    """
    Orchestrator for retrieval. 
    Manages multiple retrieval providers and a reranking strategy.
    Supports both single-source and hybrid retrieval scenarios.
    """

    ap: app.Application
    kb_id: str
    providers: List[BaseRetrievalProvider]
    reranker: BaseReranker

    def __init__(self, ap: app.Application, kb_id: str, embedding_model_uuid: str, config: Dict[str, Any] = None):
        self.ap = ap
        self.kb_id = kb_id
        self.config = config or {}
        
        # Initialize providers based on config
        self.providers = []

        # If config provides explicit providers list, use it
        providers_config = self.config.get('providers')
        
        if providers_config:
            # Explicit providers configured - use them
            for p_conf in providers_config:
                ptype = p_conf.get('type')
                self.ap.logger.info(f"Configured provider: {ptype}")
                if ptype == 'hybrid_search' or ptype == 'hybrid':
                    from .providers.hybrid import HybridSearchProvider
                    self.providers.append(
                        HybridSearchProvider(ap, kb_id, embedding_model_uuid, p_conf)
                    )
                elif ptype == 'vector_search' or ptype == 'vector':
                    from .providers.vector import VectorSearchProvider
                    self.providers.append(
                        VectorSearchProvider(ap, kb_id, embedding_model_uuid, p_conf)
                    )
                elif ptype == 'fulltext_search' or ptype == 'fulltext':
                    from .providers.fulltext import FullTextSearchProvider
                    self.providers.append(
                        FullTextSearchProvider(ap, kb_id, p_conf)
                    )
        else:
            # No explicit providers configured
            # Auto-detect VDB capabilities and choose the best provider
            self._auto_configure_default_provider(ap, kb_id, embedding_model_uuid)
        
        # Initialize Reranker
        # In future: load from config
        self.reranker = SimpleReranker(ap, self.config.get('rerank', {}))

    async def retrieve(self, query: str, top_k: int) -> List[rag_context.RetrievalResultEntry]:
        """
        Execute hybrid retrieval:
        1. Setup candidates count (usually > top_k)
        2. Parallel query all providers
        3. Fuse results (RRF)
        4. Rerank
        """
        
        # We fetch more candidates to allow effective reranking/fusion
        # If top_k is small, we ensure we get enough candidates
        candidate_k = max(top_k * 2, 20)
        
        if not self.providers:
            self.ap.logger.warning(f"No retrieval providers configured for KB {self.kb_id}")
            return []

        # 2. Parallel query
        tasks = [p.retrieve(query, candidate_k) for p in self.providers]
        results_list_of_lists = await asyncio.gather(*tasks)
        
        # 3. Fuse results (Reciprocal Rank Fusion)
        # Score = sum(1 / (k + rank))
        rrf_constant = 60
        fused_scores: Dict[str, float] = defaultdict(float)
        id_to_entry: Dict[str, rag_context.RetrievalResultEntry] = {}
        
        for results in results_list_of_lists:
            for rank, entry in enumerate(results):
                if entry.id not in id_to_entry:
                    id_to_entry[entry.id] = entry
                
                # Rank is 0-indexed, so rank+1. 
                fused_scores[entry.id] += 1.0 / (rrf_constant + rank + 1)
        
        # Sort by score descending
        sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
        
        merged_results = []
        for _id in sorted_ids:
            entry = id_to_entry[_id]
            # We could store the RRF score in metadata if needed for debugging
            # if entry.metadata:
            #     entry.metadata['rrf_score'] = fused_scores[_id]
            merged_results.append(entry)
            
        # 4. Rerank (and truncate to original top_k)
        final_results = await self.reranker.rerank(query, merged_results, top_k)

        return final_results

    def _auto_configure_default_provider(self, ap: app.Application, kb_id: str, embedding_model_uuid: str):
        """
        Auto-configure provider based on default VDB capabilities.

        Priority:
        1. hybrid_search if VDB supports 'hybrid'
        2. vector_search as fallback (all VDBs support this)

        This ensures backward compatibility when no providers are explicitly configured.
        """
        # Check if vector_db_mgr is initialized
        if not ap.vector_db_mgr:
            ap.logger.warning(
                f"VectorDBManager not initialized yet, cannot auto-configure provider for KB {kb_id}. "
                "Knowledge base will be loaded without retrieval capability until VDB is ready."
            )
            return

        # Get default VDB
        vdb = ap.vector_db_mgr.vector_db
        if not vdb:
            # Try to get first available VDB
            if ap.vector_db_mgr.databases:
                vdb = next(iter(ap.vector_db_mgr.databases.values()))

        if not vdb:
            ap.logger.error("No VDB available for auto-configuration")
            return

        # Check VDB capabilities
        capabilities = vdb.get_capabilities()
        vdb_name = 'default'  # Use 'default' as the VDB reference

        ap.logger.info(
            f"Auto-configuring retrieval provider for KB {kb_id}. "
            f"VDB: {vdb.__class__.__name__}, Capabilities: {capabilities}"
        )

        # Choose provider based on capabilities (priority: hybrid > vector)
        if 'hybrid' in capabilities:
            # VDB supports hybrid search - use it for best results
            from .providers.hybrid import HybridSearchProvider
            provider = HybridSearchProvider(
                ap, kb_id, embedding_model_uuid,
                config={'vdb': vdb_name}
            )
            ap.logger.info(f"Auto-configured HybridSearchProvider for KB {kb_id}")
        else:
            # Fallback to vector search (all VDBs support this)
            from .providers.vector import VectorSearchProvider
            provider = VectorSearchProvider(
                ap, kb_id, embedding_model_uuid,
                config={'vdb': vdb_name}
            )
            ap.logger.info(f"Auto-configured VectorSearchProvider for KB {kb_id}")

        self.providers.append(provider)
