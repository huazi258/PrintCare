import { Files } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";

export function DocumentList() {
  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">知识文档</h2>
          <p className="mt-1 text-sm text-muted-foreground">文档名称、设备归属和导入状态将在服务端提供列表能力后展示。</p>
        </div>
      </div>
      <div className="mt-4 overflow-hidden rounded-xl border border-border bg-card">
        <div className="hidden grid-cols-[minmax(0,1fr)_130px_120px_80px] gap-4 border-b border-border bg-muted/60 px-5 py-3 text-xs font-medium text-muted-foreground sm:grid">
          <span>文档名称</span><span>设备归属</span><span>导入状态</span><span>操作</span>
        </div>
        <EmptyState icon={Files} title="暂无可展示的文档列表" description="当前管理服务未提供文档列表或删除接口。本页不会以本地数据冒充知识库内容。" />
      </div>
    </section>
  );
}
