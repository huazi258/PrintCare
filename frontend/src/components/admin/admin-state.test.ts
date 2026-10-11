import { describe, expect, it } from "vitest";

import { clearSelectedFile, hasDocumentListData, importPreviewTasks, importStatusLabel } from "./admin-state";

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

  it("recognizes an empty document list", () => {
    expect(hasDocumentListData([])).toBe(false);
  });
});
