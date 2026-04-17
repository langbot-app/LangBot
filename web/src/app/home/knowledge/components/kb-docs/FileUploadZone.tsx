import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CloudUpload } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { ParserInfo } from '@/app/infra/entities/api';
import { CustomApiError, I18nObject } from '@/app/infra/entities/common';
import { extractI18nObject } from '@/i18n/I18nProvider';

interface FileUploadZoneProps {
  kbId: string;
  ragEngineName?: I18nObject;
  ragEngineCapabilities?: string[];
  onUploadSuccess: () => void;
  onUploadError: (error: string) => void;
}

export default function FileUploadZone({
  kbId,
  ragEngineName,
  ragEngineCapabilities,
  onUploadSuccess,
  onUploadError,
}: FileUploadZoneProps) {
  const { t } = useTranslation();
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  // Parser selection state
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [availableParsers, setAvailableParsers] = useState<ParserInfo[]>([]);
  const [selectedParser, setSelectedParser] = useState<string>('builtin');
  const [loadingParsers, setLoadingParsers] = useState(false);

  // Whether the Knowledge Engine natively supports document parsing.
  // This is a coarse-grained capability check rather than per-MIME-type filtering.
  // Fine-grained MIME type declaration (e.g. supported_parse_mime_types on the engine)
  // would require changes across the SDK, backend, and frontend prop chain;
  // using an engine-level capability flag keeps the change minimal.
  const ragEngineCanParse =
    ragEngineCapabilities?.includes('doc_parsing') ?? false;

  // When a file is selected, check for available parsers
  useEffect(() => {
    if (!pendingFile) return;

    const mimeType = pendingFile.type || undefined;
    setLoadingParsers(true);
    httpClient
      .listParsers(mimeType)
      .then((resp) => {
        const parsers = resp.parsers || [];
        setAvailableParsers(parsers);
        if (ragEngineCanParse) {
          setSelectedParser('builtin');
        } else if (parsers.length > 0) {
          setSelectedParser(parsers[0].plugin_id);
        } else {
          setSelectedParser('');
        }
      })
      .catch(() => {
        setAvailableParsers([]);
      })
      .finally(() => {
        setLoadingParsers(false);
      });
  }, [pendingFile, ragEngineCanParse]);

  const doUpload = useCallback(
    async (file: File, parserPluginId?: string) => {
      setIsUploading(true);
      const toastId = toast.loading(t('knowledge.documentsTab.uploadingFile'));

      try {
        // Step 1: Upload file to server
        const uploadResult = await httpClient.uploadDocumentFile(file);

        // Step 2: Associate file with knowledge base (with optional parser)
        await httpClient.uploadKnowledgeBaseFile(
          kbId,
          uploadResult.file_id,
          parserPluginId,
        );

        toast.success(t('knowledge.documentsTab.uploadSuccess'), {
          id: toastId,
        });
        onUploadSuccess();
      } catch (error) {
        console.error('File upload failed:', error);
        const errorMessage =
          t('knowledge.documentsTab.uploadError') +
          (error as CustomApiError).msg;
        toast.error(errorMessage, { id: toastId });
        onUploadError(errorMessage);
      } finally {
        setIsUploading(false);
        setPendingFile(null);
        setAvailableParsers([]);
        setSelectedParser('builtin');
      }
    },
    [kbId, onUploadSuccess, onUploadError, t],
  );

  const handleFileSelected = useCallback(
    async (file: File) => {
      if (isUploading) return;

      // Check file size (10MB limit)
      const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
      if (file.size > MAX_FILE_SIZE) {
        toast.error(t('knowledge.documentsTab.fileSizeExceeded'));
        return;
      }

      // Set loadingParsers=true BEFORE pendingFile so both state updates
      // batch together in the same render. This prevents the auto-upload
      // effect from firing before parser fetch completes.
      setLoadingParsers(true);
      setPendingFile(file);
    },
    [isUploading, t],
  );

  // Auto-upload if Knowledge Engine can parse and no external parsers available
  useEffect(() => {
    if (
      pendingFile &&
      !loadingParsers &&
      ragEngineCanParse &&
      availableParsers.length === 0
    ) {
      doUpload(pendingFile);
    }
  }, [
    pendingFile,
    loadingParsers,
    ragEngineCanParse,
    availableParsers,
    doUpload,
  ]);

  const handleConfirmUpload = useCallback(() => {
    if (!pendingFile) return;
    const parserPluginId =
      selectedParser === 'builtin' ? undefined : selectedParser;
    doUpload(pendingFile, parserPluginId);
  }, [pendingFile, selectedParser, doUpload]);

  const handleCancelUpload = useCallback(() => {
    setPendingFile(null);
    setAvailableParsers([]);
    setSelectedParser('builtin');
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        handleFileSelected(files[0]);
      }
    },
    [handleFileSelected],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFileSelected(files[0]);
      }
      // Reset the input so the same file can be selected again
      e.target.value = '';
    },
    [handleFileSelected],
  );

  // Show parser selection UI when there are choices to make, or when no parser is available
  const showParserSelector =
    pendingFile &&
    !loadingParsers &&
    (availableParsers.length > 0 || !ragEngineCanParse);

  const noParserAvailable = !ragEngineCanParse && availableParsers.length === 0;

  return (
    <Card className="mb-4">
      <CardContent className="p-4">
        {showParserSelector ? (
          <div className="space-y-3">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {pendingFile.name}
            </p>
            {noParserAvailable ? (
              <div className="rounded-md bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 p-3">
                <p className="text-sm text-yellow-800 dark:text-yellow-200">
                  {t('knowledge.documentsTab.noParserAvailable')}
                </p>
                <Link
                  to="/home/market?category=Parser"
                  className="text-sm text-primary hover:underline mt-1 inline-block"
                >
                  {t('knowledge.documentsTab.installParserHint')}
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                <label className="text-sm text-gray-600 dark:text-gray-400">
                  {t('knowledge.documentsTab.selectParser')}
                </label>
                <Select
                  value={selectedParser}
                  onValueChange={setSelectedParser}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ragEngineCanParse && (
                      <SelectItem value="builtin">
                        {ragEngineName
                          ? extractI18nObject(ragEngineName)
                          : t('knowledge.documentsTab.builtInParser')}
                      </SelectItem>
                    )}
                    {availableParsers.map((parser) => (
                      <SelectItem
                        key={parser.plugin_id}
                        value={parser.plugin_id}
                      >
                        {extractI18nObject(parser.name)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={handleCancelUpload}>
                {t('knowledge.documentsTab.cancelUpload')}
              </Button>
              {!noParserAvailable && (
                <Button size="sm" onClick={handleConfirmUpload}>
                  {t('knowledge.documentsTab.confirmUpload')}
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div
            className={`
              relative border-2 border-dashed rounded-lg p-4 text-center transition-colors
              ${
                isDragOver
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }
              ${isUploading || loadingParsers ? 'opacity-50 pointer-events-none' : ''}
            `}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              type="file"
              id="file-upload"
              className="hidden"
              onChange={handleFileSelect}
              accept=".pdf,.doc,.docx,.txt,.md,.html,.zip"
              disabled={isUploading || loadingParsers}
            />

            <label htmlFor="file-upload" className="cursor-pointer block">
              <div className="space-y-2">
                <div className="mx-auto w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
                  <CloudUpload className="w-5 h-5 text-gray-400" />
                </div>

                <div>
                  <p className="text-base font-medium text-gray-900 dark:text-gray-100">
                    {isUploading
                      ? t('knowledge.documentsTab.uploading')
                      : t('knowledge.documentsTab.dragAndDrop')}
                  </p>
                  <p className="text-xs text-gray-500 mt-1 dark:text-gray-400">
                    {t('knowledge.documentsTab.supportedFormats')}
                  </p>
                </div>
              </div>
            </label>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
