import { DateRange, TimeRangeOption } from '../types/monitoring';

/**
 * Get date range based on preset time range option
 */
export function getPresetDateRange(option: TimeRangeOption): DateRange | null {
  if (option === 'custom') return null;

  const now = new Date();
  const from = new Date();

  switch (option) {
    case 'lastHour':
      from.setHours(now.getHours() - 1);
      break;
    case 'last6Hours':
      from.setHours(now.getHours() - 6);
      break;
    case 'last24Hours':
      from.setHours(now.getHours() - 24);
      break;
    case 'last7Days':
      from.setDate(now.getDate() - 7);
      break;
    case 'last30Days':
      from.setDate(now.getDate() - 30);
      break;
    default:
      return null;
  }

  return { from, to: now };
}

/**
 * Format timestamp to readable string
 */
export function formatTimestamp(date: Date): string {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return `${seconds}s ago`;
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;

  return date.toLocaleString();
}

/**
 * Format date to YYYY-MM-DD
 */
export function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Format date to YYYY-MM-DD HH:MM:SS
 */
export function formatDateTime(date: Date): string {
  const dateStr = formatDate(date);
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${dateStr} ${hours}:${minutes}:${seconds}`;
}

/**
 * Format duration in seconds to readable string
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

/**
 * Check if date is within range
 */
export function isDateInRange(
  date: Date,
  range: DateRange | null,
): boolean {
  if (!range) return true;
  return date >= range.from && date <= range.to;
}

/**
 * Parse date string to Date object
 */
export function parseDate(dateStr: string): Date {
  return new Date(dateStr);
}
