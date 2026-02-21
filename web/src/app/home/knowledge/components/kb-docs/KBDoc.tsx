import { useCallback, useEffect, useRef, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { KnowledgeBaseFile } from '@/app/infra/entities/api';
import { columns, DocumentFile } from './documents/columns';
import { DataTable } from './documents/data-table';
import FileUploadZone from './FileUploadZone';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

export default function KBDoc({ kbId }: { kbId: string }) {
  const [documentsList, setDocumentsList] = useState<DocumentFile[]>([]);
  const { t } = useTranslation();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const getDocumentsList = useCallback(async () => {
    const resp = await httpClient.getKnowledgeBaseFiles(kbId);
    const files = resp.files.map((file: KnowledgeBaseFile) => ({
      uuid: file.uuid,
      name: file.file_name,
      status: file.status,
    }));
    setDocumentsList(files);
    return files;
  }, [kbId]);

  const startPolling = useCallback(() => {
    if (intervalRef.current) return;
    intervalRef.current = setInterval(() => {
      getDocumentsList().then((files) => {
        const allDone =
          files.length > 0 &&
          files.every(
            (doc: DocumentFile) =>
              doc.status === 'completed' || doc.status === 'failed',
          );
        if (allDone && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      });
    }, 5000);
  }, [getDocumentsList]);

  useEffect(() => {
    getDocumentsList().then((files) => {
      const hasProcessing = files.some(
        (doc: DocumentFile) =>
          doc.status !== 'completed' && doc.status !== 'failed',
      );
      if (hasProcessing) {
        startPolling();
      }
    });

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [kbId, getDocumentsList, startPolling]);

  const handleUploadSuccess = () => {
    getDocumentsList();
    startPolling();
  };

  const handleUploadError = (error: string) => {
    console.error('Upload failed:', error);
  };

  const handleDelete = (id: string) => {
    httpClient
      .deleteKnowledgeBaseFile(kbId, id)
      .then(() => {
        getDocumentsList();
        toast.success(t('knowledge.documentsTab.fileDeleteSuccess'));
      })
      .catch((error) => {
        console.error('Delete failed:', error);
        toast.error(t('knowledge.documentsTab.fileDeleteFailed'));
      });
  };

  return (
    <div className="container mx-auto py-2">
      <FileUploadZone
        kbId={kbId}
        onUploadSuccess={handleUploadSuccess}
        onUploadError={handleUploadError}
      />
      <DataTable columns={columns(handleDelete, t)} data={documentsList} />
    </div>
  );
}
