import { describe, expect, it } from "vitest";

import type { HistoryRecord } from "./history-state";
import { deletePreviewRecord, filterHistoryRecords, recordDetailKind } from "./history-state";

const records: HistoryRecord[] = [
  {
    id: "qa-preview",
    type: "qa",
    title: "如何完成 K1 的首次打印？",
    createdAt: "开发预览时间",
    messages: [],
  },
  {
    id: "diagnosis-preview",
    type: "diagnosis",
    title: "第一层无法稳定附着",
    createdAt: "开发预览时间",
    session: {
      diagnosis_id: "diagnosis-preview",
      device_id: "creality-k1",
      device_model: "Creality K1",
      original_problem: "第一层无法稳定附着",
      status: "pending_verification",
      clarification_round: 1,
      revision: 1,
      facts: [],
      rounds: [],
      decision: null,
      feedback: null,
      created_at: null,
      updated_at: null,
    },
  },
];

describe("history preview state", () => {
  it("distinguishes QA and diagnosis records", () => {
    expect(filterHistoryRecords(records, "qa", "")).toHaveLength(1);
    expect(filterHistoryRecords(records, "diagnosis", "")).toHaveLength(1);
    expect(recordDetailKind(records[0])).toBe("qa");
    expect(recordDetailKind(records[1])).toBe("diagnosis");
  });

  it("filters fixture records by type and search input", () => {
    expect(filterHistoryRecords(records, "all", "首次").map((record) => record.id)).toEqual(["qa-preview"]);
    expect(filterHistoryRecords(records, "diagnosis", "附着").map((record) => record.id)).toEqual(["diagnosis-preview"]);
    expect(filterHistoryRecords(records, "qa", "附着")).toEqual([]);
  });

  it("only removes a preview record after a confirmed local deletion", () => {
    expect(deletePreviewRecord(records, "diagnosis-preview").map((record) => record.id)).toEqual(["qa-preview"]);
    expect(records).toHaveLength(2);
  });
});
