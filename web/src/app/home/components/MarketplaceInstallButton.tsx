import { Download } from 'lucide-react';

import { Progress } from '@/components/ui/progress';

export default function MarketplaceInstallButton({
  installing,
  progress,
  disabled,
  label,
  onInstall,
}: {
  installing: boolean;
  progress: number;
  disabled: boolean;
  label: string;
  onInstall: () => void;
}) {
  const normalizedProgress = Math.max(0, Math.min(100, Math.round(progress)));

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      className="row-span-2 flex h-8 w-16 shrink-0 items-center justify-center justify-self-end rounded-md text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-45"
      onPointerDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onInstall();
      }}
    >
      {installing ? (
        <span className="flex w-14 flex-col gap-1" aria-live="polite">
          <span className="text-center text-[10px] font-medium leading-none tabular-nums text-primary">
            {normalizedProgress}%
          </span>
          <Progress value={normalizedProgress} className="h-1 bg-primary/15" />
        </span>
      ) : (
        <Download className="size-4" />
      )}
    </button>
  );
}
