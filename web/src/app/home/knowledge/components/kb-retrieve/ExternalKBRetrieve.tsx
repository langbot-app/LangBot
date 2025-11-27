'use client';

import React from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { RetrieveResult } from '@/app/infra/entities/api';
import KBRetrieveGeneric from './KBRetrieveGeneric';

interface ExternalKBRetrieveProps {
  kbId: string;
}

/**
 * External knowledge base retrieve component
 * Uses the generic retrieve component with external KB API
 */
export default function ExternalKBRetrieve({ kbId }: ExternalKBRetrieveProps) {
  const getResultTitle = (result: RetrieveResult): string => {
    // For external KB, try to get document_name or use a generic title
    return (
      (result.metadata.document_name as string) ||
      (result.metadata.source as string) ||
      result.id
    );
  };

  return (
    <KBRetrieveGeneric
      kbId={kbId}
      retrieveFunction={httpClient.retrieveExternalKnowledgeBase.bind(
        httpClient,
      )}
      getResultTitle={getResultTitle}
    />
  );
}
