import { Badge } from '@/components/ui/badge';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface AtBadgeProps {
  onRemove: () => void;
}

export default function AtBadge({ onRemove }: AtBadgeProps) {
  const { t } = useTranslation();
  return (
    <Badge
      variant="secondary"
      className="flex items-center gap-1 px-2 py-1 text-sm bg-blue-100 text-blue-600 hover:bg-blue-200"
    >
      @webchatbot
      <button
        onClick={onRemove}
        className="ml-1 hover:text-blue-800 focus:outline-none"
      >
        <X className="h-3 w-3" />
      </button>
    </Badge>
  );
}
