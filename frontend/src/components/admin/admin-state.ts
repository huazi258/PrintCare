import type { ImportTaskStatus } from "@/types/api";

export type ImportPreviewKind = "idle" | "processing" | "completed" | "failed";

export function clearSelectedFile(): null {
  return null;
}

export function importStatusLabel(status: string): string {
  if (status === "completed" || status === "success") return "已完成";
  if (status === "failed" || status === "error") return "导入失败";
  if (status === "processing" || status === "running") return "处理中";
  return status || "等待开始";
}

export function hasDocumentListData(documents: unknown[]): boolean {
  return documents.length > 0;
}

export const importPreviewTasks: Record<Exclude<ImportPreviewKind, "idle">, ImportTaskStatus> = {
  processing: {
    status: "processing",
    running_list: ["文档切分"],
    done_list: ["接收文件", "检查文件"],
    durations: {},
  },
  completed: {
    status: "completed",
    running_list: [],
    done_list: ["接收文件", "检查文件", "文档切分", "向量入库"],
    durations: {},
  },
  failed: {
    status: "failed",
    running_list: [],
    done_list: ["接收文件"],
    durations: {},
  },
};
