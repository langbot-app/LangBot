interface EventSelectOptionContentProps {
  event: string;
  label: string;
}

export default function EventSelectOptionContent({
  event,
  label,
}: EventSelectOptionContentProps) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span className="truncate font-medium">{label}</span>
      <code className="shrink-0 rounded-sm bg-muted px-1 py-0.5 font-mono text-[10px] font-normal text-muted-foreground">
        {event}
      </code>
    </span>
  );
}
