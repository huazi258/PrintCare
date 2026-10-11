import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";

const navigation = [
  { to: "/", label: "设备工作台", end: true },
  { to: "/qa", label: "知识问答" },
  { to: "/diagnosis", label: "智能诊断" },
  { to: "/history", label: "历史记录" },
  { to: "/admin", label: "知识库管理" },
];

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-lg font-semibold tracking-tight">PrintCare AI</p>
            <p className="text-sm text-muted-foreground">Creality K1 技术支持平台</p>
          </div>
          <nav aria-label="主导航" className="flex flex-wrap gap-1">
            {navigation.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted",
                    isActive && "bg-muted text-foreground",
                  )
                }
                end={item.end}
                key={item.to}
                to={item.to}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
