import { Menu, X } from "lucide-react";
import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Brand, MobileNavigation, Sidebar } from "@/components/Sidebar";

export function AppLayout() {
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Sidebar />
      <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur lg:hidden">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-4">
          <Brand />
          <button
            aria-controls="mobile-navigation"
            aria-expanded={mobileNavigationOpen}
            aria-label={mobileNavigationOpen ? "收起导航" : "展开导航"}
            className="flex size-10 items-center justify-center rounded-lg text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setMobileNavigationOpen((open) => !open)}
            type="button"
          >
            {mobileNavigationOpen ? <X aria-hidden="true" size={20} /> : <Menu aria-hidden="true" size={20} />}
          </button>
        </div>
      </header>
      <div id="mobile-navigation">
        <MobileNavigation open={mobileNavigationOpen} onNavigate={() => setMobileNavigationOpen(false)} />
      </div>
      <main className="min-w-0 px-4 py-6 sm:px-6 sm:py-8 lg:ml-60 lg:px-10">
        <Outlet />
      </main>
    </div>
  );
}
