import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import MCPDetailContent from './MCPDetailContent';

export default function MCPPage() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <MCPDetailContent id={detailId} />;
  }

  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <p>{t('mcp.selectFromSidebar')}</p>
    </div>
  );
}
