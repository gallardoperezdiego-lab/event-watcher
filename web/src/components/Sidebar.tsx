import React from 'react';
import { Radio, LayoutDashboard, Calendar, Globe, FlaskConical, Settings2, Archive, ShieldCheck } from 'lucide-react';
import { formatTime } from './ui.js';

const NAV: Array<{ label: string; items: Array<[string, string, React.ElementType]> }> = [
  { label: 'Monitor', items: [['dashboard', 'Dashboard', LayoutDashboard], ['events', 'Events', Calendar], ['watchers', 'Watchers', Radio], ['sources', 'Sources', Globe]] },
  { label: 'Tools', items: [['test_sandbox', 'Test a source', FlaskConical]] },
  { label: 'System', items: [['settings', 'Settings', Settings2], ['backup', 'Backup & transfer', Archive], ['handover', 'Handover & ownership', ShieldCheck]] },
];

interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  unreadCount: number;
  failingCount: number;
  nextCheckTime?: string | null;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onSelectTab, unreadCount, failingCount, nextCheckTime }) => {
  const failing = failingCount > 0;
  return (
    <div className="bg-rail border-r border-line">
    <aside className="sticky top-0 h-screen box-border flex flex-col gap-5 py-4 px-3 overflow-y-auto [scrollbar-width:none]">
      <a
        href="#dashboard"
        onClick={(e) => { e.preventDefault(); onSelectTab('dashboard'); }}
        className="flex items-center gap-3 px-2 py-1 no-underline text-ink"
      >
        <span className="w-9 h-9 rounded-xl bg-accent-soft border border-accent-edge flex items-center justify-center text-accent shrink-0">
          <Radio className="w-5 h-5" strokeWidth={1.8} />
        </span>
        <span className="hidden min-[1100px]:flex flex-col gap-0.5">
          <span className="font-serif font-semibold text-[19px] leading-tight text-ink whitespace-nowrap">Event Watcher</span>
          <span className="text-xs text-ink3">Local monitor · v1.1</span>
        </span>
      </a>

      <nav aria-label="Main" className="flex flex-col gap-5">
        {NAV.map((group) => (
          <div key={group.label} className="flex flex-col gap-0.5">
            <div className="ew-caps px-3 pb-2 hidden min-[1100px]:block">{group.label}</div>
            {group.items.map(([id, label, Icon]) => {
              const on = activeTab === id;
              const badge = id === 'events' && unreadCount ? unreadCount : id === 'sources' && failingCount ? failingCount : 0;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => onSelectTab(id)}
                  aria-current={on ? 'page' : undefined}
                  title={label}
                  aria-label={label}
                  className={`relative flex items-center justify-center min-[1100px]:justify-start gap-3 min-h-10 px-3 rounded-[10px] w-full text-left text-sm cursor-pointer hover:bg-hover hover:text-ink ${
                    on ? 'bg-active text-ink font-semibold' : 'text-ink2 font-medium'
                  }`}
                >
                  <Icon className={`w-5 h-5 shrink-0 ${on ? 'text-accent' : 'text-ink3'}`} strokeWidth={1.8} />
                  <span className="hidden min-[1100px]:inline flex-1 whitespace-nowrap">{label}</span>
                  {badge > 0 && (
                    <span
                      className={`min-w-[22px] h-[22px] px-[7px] box-border rounded-lg inline-flex items-center justify-center font-mono font-semibold text-xs max-[1099px]:absolute max-[1099px]:top-0 max-[1099px]:right-0 max-[1099px]:scale-90 ${
                        id === 'sources' ? 'bg-err-soft text-err' : 'bg-accent-soft text-accent'
                      }`}
                    >
                      {badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div
        className="mt-auto flex items-center gap-2.5 p-3 rounded-xl bg-card border border-edge"
        title={failing ? 'A source needs attention' : 'Monitoring normally'}
      >
        <span
          className={`w-2.5 h-2.5 rounded-full shrink-0 mx-[3px] ${failing ? 'bg-err shadow-[0_0_0_4px_var(--err-soft)]' : 'bg-ok shadow-[0_0_0_4px_var(--ok-soft)]'}`}
        />
        <span className="hidden min-[1100px]:flex flex-col gap-[3px] min-w-0">
          <span className="text-[13px] font-medium text-ink">{failing ? `${failingCount} source${failingCount > 1 ? 's' : ''} failing` : 'All sources OK'}</span>
          <span className="text-xs text-ink3">Next check {formatTime(nextCheckTime)}</span>
        </span>
      </div>
    </aside>
    </div>
  );
};
