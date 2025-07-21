'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { RetrieveResult, KnowledgeBaseFile } from '@/app/infra/entities/api';
import { toast } from 'sonner';

interface KBRetrieveProps {
  kbId: string;
}

export default function KBRetrieve({ kbId }: KBRetrieveProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<RetrieveResult[]>([]);
  const [files, setFiles] = useState<KnowledgeBaseFile[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadFiles = async () => {
      try {
        const response = await httpClient.getKnowledgeBaseFiles(kbId);
        setFiles(response.files);
      } catch (error) {
        console.error('Failed to load files:', error);
      }
    };
    loadFiles();
  }, [kbId]);

  const handleRetrieve = async () => {
    if (!query.trim()) return;

    setLoading(true);
    try {
      setResults([]);
      const response = await httpClient.retrieveKnowledgeBase(kbId, query);
      setResults(response.results);
    } catch (error) {
      console.error('Retrieve failed:', error);
      toast.error(t('knowledge.retrieveError'));
    } finally {
      setLoading(false);
    }
  };

  const getFileName = (fileId: string) => {
    const file = files.find((f) => f.uuid === fileId);
    return file?.file_name || fileId;
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
                  <span>{getFileName(result.metadata.file_id)}</span>
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
