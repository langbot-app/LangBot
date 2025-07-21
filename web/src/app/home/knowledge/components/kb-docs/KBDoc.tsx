import { useEffect, useState } from 'react';
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

  useEffect(() => {
    getDocumentsList();

    const intervalId = setInterval(() => {
      getDocumentsList();
    }, 5000);

    return () => {
      clearInterval(intervalId);
    };
  }, [kbId]);

  async function getDocumentsList() {
    const resp = await httpClient.getKnowledgeBaseFiles(kbId);
    setDocumentsList(
      resp.files.map((file: KnowledgeBaseFile) => {
        return {
          uuid: file.uuid,
          name: file.file_name,
          status: file.status,
        };
      }),
    );
  }

  const handleUploadSuccess = () => {
    // Refresh document list after successful upload
    getDocumentsList();
  };

  const handleUploadError = (error: string) => {
    // Error messages are already handled by toast in FileUploadZone component
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
