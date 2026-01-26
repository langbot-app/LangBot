import { RAGEngineInfo } from '@/app/infra/entities/api';

export interface IKnowledgeBaseVO {
  id: string;
  name: string;
  description: string;
  embeddingModelUUID: string;
  top_k: number;
  lastUpdatedTimeAgo: string;
  // New unified fields
  ragEngine?: RAGEngineInfo;
  ragEnginePluginId?: string;
  // Type of knowledge base: 'retriever' for external KB, 'rag_engine' for new plugin-based KB
  type: 'retriever' | 'rag_engine';
}

export class KnowledgeBaseVO implements IKnowledgeBaseVO {
  id: string;
  name: string;
  description: string;
  embeddingModelUUID: string;
  top_k: number;
  lastUpdatedTimeAgo: string;
  ragEngine?: RAGEngineInfo;
  ragEnginePluginId?: string;
  type: 'retriever' | 'rag_engine';

  constructor(props: IKnowledgeBaseVO) {
    this.id = props.id;
    this.name = props.name;
    this.description = props.description;
    this.embeddingModelUUID = props.embeddingModelUUID;
    this.top_k = props.top_k;
    this.lastUpdatedTimeAgo = props.lastUpdatedTimeAgo;
    this.ragEngine = props.ragEngine;
    this.ragEnginePluginId = props.ragEnginePluginId;
    this.type = props.type;
  }

  /**
   * Check if this KB supports document management
   */
  hasDocumentCapability(): boolean {
    if (!this.ragEngine) {
      return false;
    }
    return this.ragEngine.capabilities.includes('doc_ingestion');
  }

  /**
   * Get display name for the RAG engine
   */
  getEngineName(): string {
    if (!this.ragEngine) {
      return 'Unknown';
    }
    return this.ragEngine.name;
  }
}
