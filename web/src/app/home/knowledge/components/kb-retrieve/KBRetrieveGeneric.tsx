'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTranslation } from 'react-i18next';
import { RetrieveResult } from '@/app/infra/entities/api';
import { toast } from 'sonner';

interface KBRetrieveGenericProps {
  kbId: string;
  retrieveFunction: (
    kbId: string,
    query: string,
  ) => Promise<{ results: RetrieveResult[] }>;
  getResultTitle?: (result: RetrieveResult) => string;
}

/**
 * Generic knowledge base retrieve component
 * Supports both builtin and external knowledge bases
 */
export default function KBRetrieveGeneric({
  kbId,
  retrieveFunction,
  getResultTitle,
}: KBRetrieveGenericProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<RetrieveResult[]>([]);
  const [loading, setLoading] = useState(false);

  const handleRetrieve = async () => {
    if (!query.trim()) return;

    setLoading(true);
    try {
      setResults([]);
      const response = await retrieveFunction(kbId, query);
      setResults(response.results);
    } catch (error) {
      console.error('Retrieve failed:', error);
      toast.error(t('knowledge.retrieveError'));
    } finally {
      setLoading(false);
    }
  };

  const getTitle = (result: RetrieveResult): string => {
    if (getResultTitle) {
      return getResultTitle(result);
    }
    // Default: use file_id or document_name from metadata
    return (
      (result.metadata.file_id as string) ||
      (result.metadata.document_name as string) ||
      result.id
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('knowledge.queryPlaceholder')}
          onKeyPress={(e) => e.key === 'Enter' && handleRetrieve()}
        />
        <Button onClick={handleRetrieve} disabled={loading || !query.trim()}>
          {t('knowledge.query')}
        </Button>
      </div>

      <div className="space-y-3">
        {results.length === 0 && !loading && (
          <p className="text-muted-foreground">{t('knowledge.noResults')}</p>
        )}

        {loading ? (
          <p className="text-muted-foreground">{t('common.loading')}</p>
        ) : (
          results.map((result) => (
            <Card key={result.id} className="w-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex justify-between items-center">
                  <span>{getTitle(result)}</span>
                  <span className="text-xs text-muted-foreground">
                    {t('knowledge.distance')}: {result.distance.toFixed(4)}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap">
                  {result.metadata.text}
                </p>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
