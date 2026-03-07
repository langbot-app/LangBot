import { KnowledgeEngineInfo } from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';

export interface IKnowledgeBaseVO {
  id: string;
  name: string;
  description: string;
  lastUpdatedTimeAgo: string;
  emoji?: string;
  ragEngine?: KnowledgeEngineInfo;
  ragEnginePluginId?: string;
}

export class KnowledgeBaseVO implements IKnowledgeBaseVO {
  id: string;
  name: string;
  description: string;
  lastUpdatedTimeAgo: string;
  emoji?: string;
  ragEngine?: KnowledgeEngineInfo;
  ragEnginePluginId?: string;

  constructor(props: IKnowledgeBaseVO) {
    this.id = props.id;
    this.name = props.name;
    this.description = props.description;
    this.lastUpdatedTimeAgo = props.lastUpdatedTimeAgo;
    this.emoji = props.emoji;
    this.ragEngine = props.ragEngine;
    this.ragEnginePluginId = props.ragEnginePluginId;
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
   * Get display name for the Knowledge Engine
   */
  getEngineName(): string {
    if (!this.ragEngine) {
      return 'Unknown';
    }
    return extractI18nObject(this.ragEngine.name);
  }
}
