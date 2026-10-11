import { AlertTriangle, X } from "lucide-react";

import { Button } from "@/components/ui/button";

type DeleteConfirmDialogProps = {
  recordTitle: string;
  onCancel: () => void;
  onConfirm: () => void;
};

export function DeleteConfirmDialog({ recordTitle, onCancel, onConfirm }: DeleteConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/30 p-4" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="delete-history-title" className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <span className="flex size-9 items-center justify-center rounded-lg bg-destructive/10 text-destructive"><AlertTriangle className="size-5" aria-hidden="true" /></span>
          <button type="button" onClick={onCancel} aria-label="关闭删除确认" className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"><X className="size-4" aria-hidden="true" /></button>
        </div>
        <h2 id="delete-history-title" className="mt-4 text-lg font-semibold text-foreground">删除这条历史记录？</h2>
        <p className="mt-2 break-words text-sm leading-6 text-muted-foreground">“{recordTitle}”将从历史记录中删除，删除后无法恢复。</p>
        <div className="mt-6 flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onCancel}>取消</Button>
          <Button type="button" onClick={onConfirm} className="bg-destructive hover:bg-destructive/90">确认删除</Button>
        </div>
      </section>
    </div>
  );
}
