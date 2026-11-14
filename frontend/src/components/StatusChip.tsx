import React from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Loader2, 
  MinusCircle, 
  HelpCircle 
} from 'lucide-react';

export type StatusChipState = 
  | 'Available' 
  | 'Partial' 
  | 'Unavailable' 
  | 'Loading' 
  | 'Failed' 
  | 'Needs validation'
  | (string & {});

export interface StatusChipProps {
  status: StatusChipState;
  customLabel?: string;
  className?: string;
}

const statusConfig: Record<StatusChipState, {
  icon: React.ElementType;
  bgClass: string;
  textClass: string;
  borderClass: string;
  defaultLabel: string;
  spin?: boolean;
}> = {
  Available: {
    icon: CheckCircle2,
    bgClass: 'bg-emerald-950/40',
    textClass: 'text-emerald-400',
    borderClass: 'border-emerald-600/40',
    defaultLabel: 'Available',
  },
  Partial: {
    icon: AlertTriangle,
    bgClass: 'bg-amber-950/40',
    textClass: 'text-amber-400',
    borderClass: 'border-amber-600/40',
    defaultLabel: 'Partial',
  },
  Unavailable: {
    icon: MinusCircle,
    bgClass: 'bg-slate-900/60',
    textClass: 'text-slate-400',
    borderClass: 'border-slate-700/50',
    defaultLabel: 'Unavailable',
  },
  Loading: {
    icon: Loader2,
    bgClass: 'bg-blue-950/40',
    textClass: 'text-blue-400',
    borderClass: 'border-blue-600/40',
    defaultLabel: 'Loading',
    spin: true,
  },
  Failed: {
    icon: XCircle,
    bgClass: 'bg-rose-950/40',
    textClass: 'text-rose-400',
    borderClass: 'border-rose-600/40',
    defaultLabel: 'Failed',
  },
  'Needs validation': {
    icon: HelpCircle,
    bgClass: 'bg-purple-950/40',
    textClass: 'text-purple-400',
    borderClass: 'border-purple-600/40',
    defaultLabel: 'Needs validation',
  },
};

/**
 * Reusable StatusChip complying with SPEC 3.2 & AGENTS.md:
 * - 6 required states: Available, Partial, Unavailable, Loading, Failed, Needs validation.
 * - Accessible design: Uses explicit icons + text (never color-only meaning).
 */
export const StatusChip: React.FC<StatusChipProps> = ({ 
  status, 
  customLabel,
  className = '' 
}) => {
  const normalizedKey = (status && typeof status === 'string' && status.startsWith('Unavailable'))
    ? 'Unavailable'
    : status;
  const config = (statusConfig as Record<string, typeof statusConfig.Unavailable>)[normalizedKey] || statusConfig.Unavailable;
  const Icon = config.icon;
  const label = customLabel || status || config.defaultLabel;

  return (
    <span
      role="status"
      aria-label={`Status: ${label}`}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${config.bgClass} ${config.textClass} ${config.borderClass} ${className}`}
    >
      <Icon 
        className={`w-3.5 h-3.5 shrink-0 ${config.spin ? 'animate-spin' : ''}`} 
        aria-hidden="true" 
      />
      <span>{label}</span>
    </span>
  );
};
