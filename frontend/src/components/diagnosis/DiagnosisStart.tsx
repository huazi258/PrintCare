import { ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";

type DiagnosisStartProps = {
  problem: string;
  errorMessage?: string;
  onProblemChange: (value: string) => void;
  onStart: () => void;
};

export function DiagnosisStart({
  problem,
  errorMessage,
  onProblemChange,
  onStart,
}: DiagnosisStartProps) {
  return (
    <section className="mx-auto max-w-[880px]" aria-labelledby="diagnosis-title">
      <div className="mb-8">
        <p className="text-sm font-medium text-primary">Creality K1</p>
        <h1 id="diagnosis-title" className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
          智能故障诊断
        </h1>
        <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
          描述打印过程中遇到的问题，系统将参考本地设备资料辅助排查。诊断可能按需追问，最多不超过三轮。
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-5 shadow-[0_2px_10px_rgba(27,36,48,0.04)] sm:p-6">
        <label htmlFor="diagnosis-problem" className="text-base font-semibold text-foreground">
          描述故障现象
        </label>
        <p id="diagnosis-problem-help" className="mt-1 text-sm leading-6 text-muted-foreground">
          例如出现的现象、发生时机，以及你已经尝试过的操作。
        </p>
        <textarea
          id="diagnosis-problem"
          value={problem}
          onChange={(event) => onProblemChange(event.target.value)}
          aria-describedby="diagnosis-problem-help"
          placeholder="请尽量具体地描述打印过程中遇到的问题…"
          rows={7}
          className="mt-4 min-h-40 w-full resize-y rounded-[10px] border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
        {errorMessage ? (
          <p role="alert" className="mt-3 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {errorMessage}
          </p>
        ) : null}
        <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex max-w-xl gap-2.5 rounded-lg bg-muted px-3 py-2.5 text-sm leading-5 text-muted-foreground">
            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <p>请勿在未确认安全边界时进行高温、电气或拆机操作；必要时请联系官方支持。</p>
          </div>
          <Button type="button" onClick={onStart} disabled={!problem.trim()} className="min-w-28">
            开始诊断
          </Button>
        </div>
      </div>
    </section>
  );
}
