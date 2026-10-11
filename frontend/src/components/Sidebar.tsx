import type { LucideIcon } from "lucide-react";
import { BookOpenText, BrainCircuit, Database, LayoutDashboard, Printer } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

export interface NavigationItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const primaryNavigation: NavigationItem[] = [
  { to: "/", label: "工作台", icon: LayoutDashboard, end: true },
  { to: "/qa", label: "知识问答", icon: BookOpenText },
  { to: "/diagnosis", label: "智能诊断", icon: BrainCircuit },
  { to: "/history", label: "历史记录", icon: Database },
];

const adminNavigation: NavigationItem = { to: "/admin", label: "知识库管理", icon: Database };

interface BrandProps {
  compact?: boolean;
}

export function Brand({ compact = false }: BrandProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Printer aria-hidden="true" size={19} strokeWidth={1.8} />
      </span>
      {!compact && (
        <span className="min-w-0">
          <span className="block text-sm font-semibold tracking-tight text-foreground">PrintCare AI</span>
          <span className="block text-xs text-muted-foreground">K1 技术支持</span>
        </span>
      )}
    </div>
  );
}

interface NavigationLinksProps {
  onNavigate?: () => void;
}

function NavigationLink({ item, onNavigate }: { item: NavigationItem; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <NavLink
      className={({ isActive }) =>
        cn(
          "flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
          isActive && "bg-muted text-foreground",
        )
      }
      end={item.end}
      onClick={onNavigate}
      to={item.to}
    >
      <Icon aria-hidden="true" size={18} strokeWidth={1.8} />
      {item.label}
    </NavLink>
  );
}

export function NavigationLinks({ onNavigate }: NavigationLinksProps) {
  return (
    <nav aria-label="主导航" className="flex min-h-0 flex-1 flex-col gap-1">
      {primaryNavigation.map((item) => (
        <NavigationLink item={item} key={item.to} onNavigate={onNavigate} />
      ))}
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-border bg-card px-3 py-5 lg:flex">
      <div className="px-2"><Brand /></div>
      <div className="mt-8"><NavigationLinks /></div>
      <div className="mt-auto border-t border-border pt-3">
        <NavigationLink item={adminNavigation} />
      </div>
    </aside>
  );
}

interface MobileNavigationProps {
  open: boolean;
  onNavigate: () => void;
}

export function MobileNavigation({ open, onNavigate }: MobileNavigationProps) {
  if (!open) return null;

  return (
    <div className="border-t border-border bg-card px-4 py-3 lg:hidden">
      <div className="mx-auto flex max-w-[1200px] flex-col gap-1">
        <NavigationLinks onNavigate={onNavigate} />
        <div className="my-2 border-t border-border" />
        <NavigationLink item={adminNavigation} onNavigate={onNavigate} />
      </div>
    </div>
  );
}
