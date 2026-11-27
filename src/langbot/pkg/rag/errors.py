from __future__ import annotations


class KnowledgeIngestionInProgressError(RuntimeError):
    """A knowledge-base mutation is refused because ingestion is still running.

    Surfaced to API clients as HTTP 409: the request is valid and can be retried
    once the pending/processing files settle.
    """

    code = 'knowledge_ingestion_in_progress'
