import type { DiagnosisSession } from "@/types/api";
import type { QaMessage } from "@/types/qa";

export type HistoryRecordType = "qa" | "diagnosis";

export type QaHistoryRecord = {
  id: string;
  type: "qa";
  title: string;
  createdAt: string;
  messages: QaMessage[];
};

export type DiagnosisHistoryRecord = {
  id: string;
  type: "diagnosis";
  title: string;
  createdAt: string;
  session: DiagnosisSession;
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

export function recordDetailKind(record: HistoryRecord): HistoryRecordType {
  return record.type;
}
