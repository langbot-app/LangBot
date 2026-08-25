import { Pencil } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export default function EntityTitleEditButton({
  onClick,
}: {
  onClick: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8 shrink-0 text-muted-foreground"
          aria-label={t('common.editBasicInfo')}
          onClick={onClick}
        >
          <Pencil className="size-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{t('common.editBasicInfo')}</TooltipContent>
    </Tooltip>
  );
}
