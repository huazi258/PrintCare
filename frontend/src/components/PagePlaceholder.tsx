import type { ReactNode } from "react";

interface PagePlaceholderProps {
  title: string;
  description: string;
  children?: ReactNode;
}

export function PagePlaceholder({ title, description, children }: PagePlaceholderProps) {
  return (
    <section aria-labelledby="page-title" className="max-w-3xl space-y-5">
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">PrintCare AI · T3-01</p>
        <h1 id="page-title" className="text-3xl font-semibold tracking-tight">
          {title}
        </h1>
        <p className="text-muted-foreground">{description}</p>
      </div>
      <div className="rounded-lg border border-dashed border-border bg-card p-5">
        <p className="font-medium">该业务页面尚未实现</p>
        <p className="mt-1 text-sm text-muted-foreground">
          当前仅提供工程底座、路由与通信层，不展示模拟诊断或 AI 结果。
        </p>
      </div>
      {children}
    </section>
  );
}
