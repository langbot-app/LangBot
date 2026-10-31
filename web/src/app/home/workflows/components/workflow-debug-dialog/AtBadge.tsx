import { Badge } from '@/components/ui/badge';
import { X } from 'lucide-react';

interface AtBadgeProps {
  targetName: string;
  readonly?: boolean;
  onRemove?: () => void;
}

export default function AtBadge({
  targetName,
  readonly = false,
  onRemove,
}: AtBadgeProps) {
  return (
    <Badge
      variant="secondary"
      className="flex items-center gap-1 px-2 py-1 text-sm bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/60"
    >
      @{targetName}
      {!readonly && onRemove && (
        <button
          onClick={onRemove}
          className="ml-1 hover:text-blue-800 dark:hover:text-blue-200 focus:outline-none"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </Badge>
  );
}
