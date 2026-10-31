import { useAuthenticatedPluginIcon } from '@/hooks/useAuthenticatedPluginResource';
import { cn } from '@/lib/utils';

export function AuthenticatedPluginIcon({
  author,
  name,
  alt = '',
  className,
}: {
  author: string;
  name: string;
  alt?: string;
  className?: string;
}) {
  const icon = useAuthenticatedPluginIcon(
    author,
    name,
    Boolean(author && name),
  );

  if (!icon.url || icon.error) {
    return (
      <span
        aria-hidden={alt ? undefined : true}
        aria-label={alt || undefined}
        className={cn('inline-block bg-muted', className)}
      />
    );
  }

  return <img src={icon.url} alt={alt} className={className} />;
}
