import React from 'react';
import { Calendar } from 'lucide-react';

/* Shared building blocks of the Aurora design system. */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-on-accent border-transparent font-display font-bold shadow-[var(--glow)] hover:brightness-110',
  secondary: 'bg-transparent text-ink border-steel font-medium hover:bg-hover',
  ghost: 'bg-transparent text-accent border-transparent font-semibold hover:bg-accent-soft',
  danger: 'bg-err-soft text-err border-err-edge font-semibold hover:brightness-110',
};

export const Button: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: ButtonVariant;
    icon?: React.ReactNode;
    iconRight?: React.ReactNode;
    fullWidth?: boolean;
  }
> = ({ variant = 'primary', icon, iconRight, fullWidth, className = '', children, type = 'button', ...rest }) => (
  <button
    type={type}
    className={`inline-flex items-center justify-center gap-2 min-h-9 px-3.5 py-2 rounded-xl border text-[13px] tracking-[0.01em] cursor-pointer transition active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap ${VARIANTS[variant]} ${fullWidth ? 'w-full' : ''} ${className}`}
    {...rest}
  >
    {icon}
    {children !== undefined && children !== null && children !== false && <span>{children}</span>}
    {iconRight}
  </button>
);

export const IconButton: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; tone?: 'default' | 'danger' | 'bordered' }
> = ({ label, tone = 'default', className = '', children, type = 'button', ...rest }) => {
  const tones = {
    default: 'text-ink2 hover:bg-hover hover:text-ink border-transparent',
    danger: 'text-ink3 hover:bg-err-soft hover:text-err border-transparent',
    bordered: 'text-ink2 hover:bg-hover hover:text-ink border-edge bg-card',
  };
  return (
    <button
      type={type}
      title={label}
      aria-label={label}
      className={`w-10 h-10 shrink-0 inline-flex items-center justify-center rounded-xl border cursor-pointer transition disabled:opacity-40 ${tones[tone]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
};

export const Switch: React.FC<{ checked: boolean; onChange: (v: boolean) => void; labelledBy: string }> = ({
  checked,
  onChange,
  labelledBy,
}) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-labelledby={labelledBy}
    onClick={() => onChange(!checked)}
    className={`relative w-12 h-7 shrink-0 mt-0.5 rounded-full border cursor-pointer transition-colors ${
      checked ? 'bg-accent border-accent' : 'bg-well border-field-edge'
    }`}
  >
    <span
      className={`absolute top-[3px] w-5 h-5 rounded-full transition-[left] ${checked ? 'left-[23px] bg-on-accent' : 'left-[3px] bg-ink3'}`}
    />
  </button>
);

/** Big calendar-style date tile used on event cards. */
export const DateTile: React.FC<{ date: string | null; compact?: boolean }> = ({ date, compact }) => {
  const parts = dateParts(date);
  return (
    <div
      className={`${compact ? 'basis-16 py-3' : 'basis-[72px] py-3.5'} shrink-0 grow-0 flex flex-col items-center gap-1.5 rounded-xl bg-raised border border-edge text-center`}
    >
      {parts ? (
        <>
          <span className="ew-caps">{parts.dow}</span>
          <span className={`font-display font-semibold tracking-[-0.02em] text-ink leading-none ${compact ? 'text-[26px]' : 'text-[30px]'}`}>
            {parts.day}
          </span>
          <span className="text-xs font-medium text-ink2">{parts.monYear}</span>
        </>
      ) : (
        <>
          <Calendar className="w-5 h-5 text-ink3" strokeWidth={1.8} />
          <span className="text-xs font-medium leading-tight text-ink3">
            Date
            <br />
            TBC
          </span>
        </>
      )}
    </div>
  );
};

export const EmptyState: React.FC<{ icon?: React.ReactNode; title: string; children?: React.ReactNode }> = ({
  icon,
  title,
  children,
}) => (
  <div className="px-6 py-10 rounded-2xl border border-dashed border-field-edge flex flex-col items-center gap-2 text-center">
    {icon && <span className="text-ink3">{icon}</span>}
    <div className="font-serif font-semibold text-lg text-ink">{title}</div>
    {children}
  </div>
);

/** Segmented control (All / New / Starred …). */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  mono,
}: {
  options: Array<[T, string]>;
  value: T;
  onChange: (v: T) => void;
  label: string;
  mono?: boolean;
}) {
  return (
    <div role="group" aria-label={label} className="flex gap-0.5 p-[3px] rounded-xl bg-card border border-edge">
      {options.map(([v, l]) => (
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          onClick={() => onChange(v)}
          className={`${mono ? 'h-8 px-2.5 text-xs font-mono' : 'h-9 px-3.5 text-sm'} font-medium rounded-[9px] cursor-pointer whitespace-nowrap ${
            value === v ? 'bg-active text-ink' : 'text-ink3 hover:text-ink'
          }`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- formatting helpers */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/** "Fri 02 Oct 2026" (as stored by the backend) -> { dow, day, monYear }. */
export function dateParts(date: string | null | undefined): { dow: string; day: string; monYear: string } | null {
  if (!date) return null;
  const m = date.match(/^([A-Za-z]{3})[a-z]*,?\s+(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})/);
  if (m) return { dow: m[1], day: String(Number(m[2])), monYear: `${m[3]} ${m[4]}` };
  const d = new Date(date);
  if (!isNaN(d.getTime())) return { dow: DAYS[d.getDay()], day: String(d.getDate()), monYear: `${MONTHS[d.getMonth()]} ${d.getFullYear()}` };
  return null;
}

export function shortDate(date: string | null | undefined): string {
  const p = dateParts(date);
  return p ? `${p.day} ${p.monYear.slice(0, 4)}${p.monYear.slice(-2)}` : 'Date TBC';
}

export function formatWhen(iso?: string | null): string {
  if (!iso) return 'never';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return `${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function formatTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

export function intervalLabel(m: number): string {
  if (m < 60) return `${m} min`;
  if (m % 60) return `${m} min`;
  return m === 60 ? '1 hour' : `${m / 60} hours`;
}

export function intervalShort(m: number): string {
  return m >= 60 && m % 60 === 0 ? `${m / 60}h` : `${m}m`;
}

export const TYPE_OPTIONS: Array<[string, string]> = [
  ['rss', 'RSS feed'],
  ['atom', 'Atom feed'],
  ['webpage', 'Normal webpage (change monitor)'],
  ['event_listing', 'Event listing webpage'],
  ['sports_fixture', 'Sports fixture webpage'],
  ['calendar_ics', 'Public calendar / ICS feed'],
  ['json_feed', 'JSON events feed'],
  ['custom_url', 'Custom URL'],
];

export const TYPE_SHORT: Record<string, string> = {
  rss: 'RSS feed',
  atom: 'RSS feed',
  calendar_ics: 'iCal calendar',
  sports_fixture: 'Sports fixture',
  event_listing: 'Event listing',
  webpage: 'Webpage',
  json_feed: 'JSON feed',
  custom_url: 'Custom URL',
};

export const INTERVAL_OPTIONS: Array<[number, string]> = [
  [30, 'Every 30 minutes'],
  [60, 'Every hour'],
  [180, 'Every 3 hours'],
  [360, 'Every 6 hours'],
  [720, 'Every 12 hours'],
  [1440, 'Every 24 hours (gentle)'],
];
