import { Link } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import { ArrowRight } from 'lucide-react';

/**
 * One "what now" row: icon, label, chevron.
 *
 * Both the follow-up steps and the pending-permission review use this so a
 * finished install always looks the same regardless of which line it shows.
 * Kept as a link so the row is navigable and keyboard-focusable; `label` is
 * the full phrase for assistive tech when `text` is shortened for the eye.
 */
export default function PluginNextStepRow({
  to,
  icon: Icon,
  text,
  label,
  onNavigate,
}: {
  to: string;
  icon: LucideIcon;
  text: string;
  label?: string;
  onNavigate?: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      aria-label={label}
      className="flex items-center gap-1.5 text-xs text-green-700 hover:underline dark:text-green-300"
    >
      <Icon className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
      <span className="flex-1">{text}</span>
      <ArrowRight className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
    </Link>
  );
}
