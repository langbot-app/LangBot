export default function DockIcon({ kind }: { kind: string }) {
  const paths: Record<string, string> = {
    event: 'M13 2 4 14h7l-1 8 10-12h-7l0-8z',
    activity: 'M3 12h4l3-8 4 16 3-8h4',
    bot: 'M8 4h8v3H8z M5 7h14v13H5z M9 12h.01 M15 12h.01 M9 16h6',
    pipeline: 'M4 3h6v6H4z M14 15h6v6h-6z M7 9v9h7',
    agent: 'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M4 21v-2a8 8 0 0 1 16 0v2',
    processor: 'M9 3h6v6h6v6h-6v6H9v-6H3V9h6z',
    completed: 'm5 12 4 4L19 6',
    failed: 'm6 6 12 12 M6 18 18 6',
    cancelled: 'm6 6 12 12 M6 18 18 6',
    queued: 'M8 5v14 M16 5v14',
    waiting: 'M8 5v14 M16 5v14',
    move: 'm8 6 4-4 4 4 M12 2v20 m-4-4 4 4 4-4',
    collapse: 'm9 5 7 7-7 7',
  };
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[kind] || paths.activity} />
    </svg>
  );
}
