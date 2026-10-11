import { FlaskConical } from "lucide-react";

type DiagnosisPreviewState =
  | "start"
  | "ask-one"
  | "ask-two"
  | "ask-three"
  | "processing"
  | "answer-pending"
  | "answer-resolved"
  | "answer-unresolved"
  | "insufficient"
  | "error";

type DiagnosisPreviewControlsProps = {
  value: DiagnosisPreviewState;
  onChange: (state: DiagnosisPreviewState) => void;
};

const previewStates: { value: DiagnosisPreviewState; label: string }[] = [
  { value: "start", label: "初始" },
  { value: "ask-one", label: "1 题 / 第 1 轮" },
  { value: "ask-two", label: "2 题 / 第 2 轮" },
  { value: "ask-three", label: "3 题 / 第 3 轮" },
  { value: "processing", label: "处理中" },
  { value: "answer-pending", label: "结论待验证" },
  { value: "answer-resolved", label: "已解决" },
  { value: "answer-unresolved", label: "未解决" },
  { value: "insufficient", label: "资料不足" },
  { value: "error", label: "错误" },
];

export type { DiagnosisPreviewState };

export function DiagnosisPreviewControls({ value, onChange }: DiagnosisPreviewControlsProps) {
  return (
    <section className="mb-6 rounded-xl border border-dashed border-primary/35 bg-primary/5 p-4" aria-label="开发预览控制">
      <div className="flex items-start gap-2 text-sm text-primary">
        <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p><span className="font-semibold">开发预览（模拟数据）</span>：仅用于检查界面状态，不代表真实设备资料、诊断推理或会话状态。</p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {previewStates.map((state) => (
          <button
            type="button"
            key={state.value}
            onClick={() => onChange(state.value)}
            aria-pressed={value === state.value}
            className={`rounded-lg border px-2.5 py-1.5 text-xs font-medium transition focus:outline-none focus:ring-2 focus:ring-primary/30 ${
              value === state.value ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground"
            }`}
          >
            {state.label}
          </button>
        ))}
      </div>
    </section>
  );
}
