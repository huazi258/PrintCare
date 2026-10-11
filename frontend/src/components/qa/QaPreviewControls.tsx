import type { QaPreviewState } from "@/pages/QaPage";
import { cn } from "@/lib/utils";

const options: Array<{ value: QaPreviewState; label: string }> = [
  { value: "welcome", label: "初始" },
  { value: "generating", label: "生成中" },
  { value: "complete", label: "完成" },
  { value: "error", label: "失败" },
  { value: "no-sources", label: "无来源" },
];

interface QaPreviewControlsProps {
  state: QaPreviewState;
  onChange: (state: QaPreviewState) => void;
}

export function QaPreviewControls({ state, onChange }: QaPreviewControlsProps) {
  return (
    <aside aria-label="开发预览状态" className="mb-6 rounded-lg border border-dashed border-border bg-muted/40 p-3">
      <p className="text-xs font-medium text-muted-foreground">开发预览：以下状态仅用于 UI 验证，不来自知识库或真实服务。</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            className={cn("rounded-md px-2.5 py-1 text-xs outline-none transition-colors hover:bg-card focus-visible:ring-2 focus-visible:ring-ring", state === option.value ? "bg-card text-primary shadow-sm" : "text-muted-foreground")}
            key={option.value}
            onClick={() => onChange(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </aside>
  );
}
