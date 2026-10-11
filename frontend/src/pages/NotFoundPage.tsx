import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <section className="max-w-2xl space-y-4">
      <p className="text-sm font-medium text-muted-foreground">404</p>
      <h1 className="text-3xl font-semibold tracking-tight">未找到页面</h1>
      <p className="text-muted-foreground">该地址不属于 PrintCare AI 当前提供的页面。</p>
      <Button asChild variant="outline">
        <Link to="/">返回设备工作台</Link>
      </Button>
    </section>
  );
}
