import { describe, expect, it } from "vitest";

import {
  IMPORT_MAX_POLL_ATTEMPTS,
  canStartImport,
  clearSelectedFile,
  hasDocumentListData,
  importPreviewTasks,
  importStatusLabel,
  isImportTaskFailure,
  isImportTaskTerminal,
  shouldContinueImportPolling,
} from "./admin-state";

describe("admin preview state", () => {
  it("clears a selected file value", () => {
    expect(clearSelectedFile()).toBeNull();
  });

  it("does not turn an unintegrated upload into a success state", () => {
    expect(importStatusLabel("waiting")).toBe("waiting");
    expect(importStatusLabel(importPreviewTasks.processing.status)).toBe("处理中");
  });

  it("renders task labels for processing, completion, and failure", () => {
    expect(importStatusLabel(importPreviewTasks.completed.status)).toBe("已完成");
    expect(importStatusLabel(importPreviewTasks.failed.status)).toBe("导入失败");
  });

  it("stops polling only after a terminal status or the bounded attempt count", () => {
    expect(isImportTaskTerminal("completed")).toBe(true);
    expect(isImportTaskTerminal("failed")).toBe(true);
    expect(isImportTaskFailure("failed")).toBe(true);
    expect(isImportTaskFailure("completed")).toBe(false);
    expect(shouldContinueImportPolling("processing", IMPORT_MAX_POLL_ATTEMPTS - 1)).toBe(true);
    expect(shouldContinueImportPolling("processing", IMPORT_MAX_POLL_ATTEMPTS)).toBe(false);
    expect(shouldContinueImportPolling("completed", 1)).toBe(false);
  });

  it("does not permit another upload while the current one is active", () => {
    expect(canStartImport(false, false)).toBe(false);
    expect(canStartImport(true, true)).toBe(false);
    expect(canStartImport(true, false)).toBe(true);
  });

  it("recognizes an empty document list", () => {
    expect(hasDocumentListData([])).toBe(false);
  });
});
