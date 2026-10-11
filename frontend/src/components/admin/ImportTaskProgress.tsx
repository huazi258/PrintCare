import { AlertCircle, CheckCircle2, LoaderCircle } from "lucide-react";

import type { ImportTaskStatus } from "@/types/api";

import { importStatusLabel } from "./admin-state";

type ImportTaskProgressProps = {
  task: ImportTaskStatus;
  errorMessage?: string;
};

export function ImportTaskProgress({ task, errorMessage }: ImportTaskProgressProps) {
  const isError = task.status === "failed" || task.status === "error";
  const isComplete = task.status === "completed" || task.status === "success";
  const StatusIcon = isError ? AlertCircle : isComplete ? CheckCircle2 : LoaderCircle;
  const allSteps = [...task.done_list, ...task.running_list];

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-3">
        <span className={`flex size-9 items-center justify-center rounded-lg ${isError ? "bg-destructive/10 text-destructive" : isComplete ? "bg-emerald-50 text-emerald-700" : "bg-primary/10 text-primary"}`}>
          <StatusIcon className={`size-5 ${!isError && !isComplete ? "animate-spin" : ""}`} aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-base font-semibold text-foreground">导入任务状态</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">{importStatusLabel(task.status)}</p>
        </div>
      </div>
      <div className="mt-5 grid gap-2">
        {allSteps.length ? allSteps.map((step) => {
          const isRunning = task.running_list.includes(step);
          return <div key={step} className="flex items-center justify-between rounded-lg bg-muted/60 px-3 py-2 text-sm"><span className="text-foreground">{step}</span><span className="text-xs text-muted-foreground">{isRunning ? "正在执行" : "已完成"}</span></div>;
        }) : <p className="text-sm text-muted-foreground">尚未返回可展示的导入步骤。</p>}
      </div>
      {errorMessage ? <p role="alert" className="mt-4 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{errorMessage}</p> : null}
    </section>
  );
}
