import type { ProcessorRun } from '@/app/infra/entities/api';

function milliseconds(
  precise: number | null | undefined,
  seconds: number | null | undefined,
) {
  if (typeof precise === 'number' && Number.isFinite(precise)) return precise;
  if (typeof seconds === 'number' && Number.isFinite(seconds))
    return seconds * 1000;
  return null;
}

export function processorRunDuration(run: ProcessorRun): number | null {
  const start = milliseconds(run.started_at_ms, run.started_at);
  const end = milliseconds(run.finished_at_ms, run.finished_at);
  return start !== null && end !== null && end >= start ? end - start : null;
}

export function formatRunDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)} s`;
  return `${(ms / 60000).toFixed(1)} min`;
}
