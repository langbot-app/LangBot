import React, { useCallback, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

interface FileUploadZoneProps {
  kbId: string;
  onUploadSuccess: () => void;
  onUploadError: (error: string) => void;
}

export default function FileUploadZone({
  kbId,
  onUploadSuccess,
  onUploadError,
}: FileUploadZoneProps) {
  const { t } = useTranslation();
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const handleUpload = useCallback(
    async (file: File) => {
      if (isUploading) return;

      setIsUploading(true);
      const toastId = toast.loading(t('knowledge.documentsTab.uploadingFile'));

      try {
        // Step 1: Upload file to server
        const uploadResult = await httpClient.uploadDocumentFile(file);

        // Step 2: Associate file with knowledge base
        await httpClient.uploadKnowledgeBaseFile(kbId, uploadResult.file_id);

        toast.success(t('knowledge.documentsTab.uploadSuccess'), {
          id: toastId,
        });
        onUploadSuccess();
      } catch (error) {
        console.error('File upload failed:', error);
        const errorMessage = t('knowledge.documentsTab.uploadError');
        toast.error(errorMessage, { id: toastId });
        onUploadError(errorMessage);
      } finally {
        setIsUploading(false);
      }
    },
    [kbId, isUploading, onUploadSuccess, onUploadError],
  );

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
        handleUpload(files[0]);
      }
    },
    [handleUpload],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleUpload(files[0]);
      }
    },
    [handleUpload],
  );

  return (
    <Card className="mb-4">
      <CardContent className="p-4">
        <div
          className={`
            relative border-2 border-dashed rounded-lg p-4 text-center transition-colors
            ${
              isDragOver
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            }
            ${isUploading ? 'opacity-50 pointer-events-none' : ''}
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
            accept=".pdf,.doc,.docx,.txt,.md,.html"
            disabled={isUploading}
          />

          <label htmlFor="file-upload" className="cursor-pointer block">
            <div className="space-y-2">
              <div className="mx-auto w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              </div>

              <div>
                <p className="text-base font-medium text-gray-900">
                  {isUploading
                    ? t('knowledge.documentsTab.uploading')
                    : t('knowledge.documentsTab.dragAndDrop')}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {t('knowledge.documentsTab.supportedFormats')}
                </p>
              </div>
            </div>
          </label>
        </div>
      </CardContent>
    </Card>
  );
}
