import { ChevronRight, ClipboardList, MessageSquareText } from "lucide-react";

import type { HistoryRecord } from "./history-state";

type HistoryListProps = {
  records: HistoryRecord[];
  onSelect: (record: HistoryRecord) => void;
};

const diagnosisStatusLabels = {
  in_progress: "进行中",
  pending_verification: "待验证",
  resolved: "已解决",
  unresolved: "未解决",
  insufficient: "资料不足",
  ended: "已结束",
};

export function HistoryList({ records, onSelect }: HistoryListProps) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      {records.map((record) => {
        const isDiagnosis = record.type === "diagnosis";
        const Icon = isDiagnosis ? ClipboardList : MessageSquareText;
        const status = isDiagnosis ? diagnosisStatusLabels[record.session.status] : null;

        return (
          <button
            type="button"
            key={record.id}
            onClick={() => onSelect(record)}
            className="flex w-full items-center gap-3 border-b border-border px-4 py-4 text-left transition last:border-b-0 hover:bg-muted/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary sm:px-5"
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-primary"><Icon className="size-4.5" aria-hidden="true" /></span>
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="truncate text-sm font-semibold text-foreground">{record.title}</span>
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{isDiagnosis ? "智能诊断" : "知识问答"}</span>
                {status ? <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">{status}</span> : null}
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">{record.createdAt}</span>
            </span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
