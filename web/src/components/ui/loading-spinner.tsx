import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LoadingSpinnerProps {
  /**
   * Size variant of the spinner
   * @default 'default'
   */
  size?: 'sm' | 'default' | 'lg';
  /**
   * Additional CSS classes
   */
  className?: string;
  /**
   * Loading text to display below the spinner
   */
  text?: string;
  /**
   * Whether to display as full page overlay
   * @default false
   */
  fullPage?: boolean;
}

const sizeMap = {
  sm: 'h-4 w-4',
  default: 'h-8 w-8',
  lg: 'h-12 w-12',
};

const textSizeMap = {
  sm: 'text-xs',
  default: 'text-sm',
  lg: 'text-base',
};

export function LoadingSpinner({
  size = 'default',
  className,
  text = '加载中...',
  fullPage = false,
}: LoadingSpinnerProps) {
  const spinner = (
    <div className="flex flex-col items-center gap-4">
      <Loader2
        className={cn('animate-spin text-primary', sizeMap[size], className)}
      />
      {text && (
        <p className={cn('text-muted-foreground', textSizeMap[size])}>{text}</p>
      )}
    </div>
  );

  if (fullPage) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        {spinner}
      </div>
    );
  }

  return spinner;
}

/**
 * Full page loading component for use in page.tsx or layout.tsx
 */
export function LoadingPage({ text }: { text?: string }) {
  return <LoadingSpinner fullPage text={text} />;
}

/**
 * Inline loading component for use within components
 */
export function LoadingInline({
  size,
  text,
}: {
  size?: 'sm' | 'default' | 'lg';
  text?: string;
}) {
  return <LoadingSpinner size={size} text={text} />;
}
