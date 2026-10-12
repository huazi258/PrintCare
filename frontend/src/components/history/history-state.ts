import type { DiagnosisSession } from "@/types/api";
import type { QaMessage } from "@/types/qa";

export type HistoryRecordType = "qa" | "diagnosis";

export type QaHistoryRecord = {
  id: string;
  type: "qa";
  title: string;
  createdAt: string;
  sortTimestamp?: number;
  sessionId: string;
  messages: QaMessage[];
  isPreview?: boolean;
};

export type DiagnosisHistoryRecord = {
  id: string;
  type: "diagnosis";
  title: string;
  createdAt: string;
  session: DiagnosisSession;
  isPreview?: boolean;
};

export type HistoryRecord = QaHistoryRecord | DiagnosisHistoryRecord;
export type HistoryFilter = "all" | HistoryRecordType;

export function filterHistoryRecords(
  records: HistoryRecord[],
  filter: HistoryFilter,
  query: string,
): HistoryRecord[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  return records.filter((record) => {
    const matchesType = filter === "all" || record.type === filter;
    const matchesQuery = !normalizedQuery || record.title.toLocaleLowerCase().includes(normalizedQuery);
    return matchesType && matchesQuery;
  });
}

export function deletePreviewRecord(records: HistoryRecord[], recordId: string): HistoryRecord[] {
  return records.filter((record) => record.id !== recordId);
}

export function sortHistoryRecords(records: HistoryRecord[]): HistoryRecord[] {
  return [...records].sort((left, right) => {
    const leftTime = left.type === "qa"
      ? left.sortTimestamp ?? Date.parse(left.createdAt)
      : Date.parse(left.session.updated_at ?? left.session.created_at ?? "");
    const rightTime = right.type === "qa"
      ? right.sortTimestamp ?? Date.parse(right.createdAt)
      : Date.parse(right.session.updated_at ?? right.session.created_at ?? "");
    return (Number.isNaN(rightTime) ? 0 : rightTime) - (Number.isNaN(leftTime) ? 0 : leftTime);
  });
}

export function removeHistoryRecord(records: HistoryRecord[], recordId: string): HistoryRecord[] {
  return records.filter((record) => record.id !== recordId);
}

export function recordDetailKind(record: HistoryRecord): HistoryRecordType {
  return record.type;
}
