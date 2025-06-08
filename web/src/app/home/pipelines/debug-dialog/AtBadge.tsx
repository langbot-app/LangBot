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
      className="flex items-center gap-1 px-2 py-1 text-sm bg-blue-100 text-blue-600 hover:bg-blue-200"
    >
      @{targetName}
      {!readonly && onRemove && (
        <button
          onClick={onRemove}
          className="ml-1 hover:text-blue-800 focus:outline-none"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </Badge>
  );
}
