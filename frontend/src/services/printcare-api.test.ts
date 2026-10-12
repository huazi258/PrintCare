import { afterEach, describe, expect, it, vi } from "vitest";

import { printCareApi } from "@/services/printcare-api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("printCareApi management requests", () => {
  it("sends the in-memory key only with the document upload request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ message: "文件上传成功", task_id: "task-k1" }), {
        headers: { "content-type": "application/json" },
      }),
    );

    await printCareApi.uploadDocument(
      new File(["# manual"], "manual.md", { type: "text/markdown" }),
      "creality-k1",
      "test-admin-key",
    );

    const [, request] = fetchMock.mock.calls[0];
    expect(request?.credentials).toBe("include");
    expect(new Headers(request?.headers).get("X-PrintCare-Admin-Key")).toBe("test-admin-key");
  });

  it("sends the in-memory key when reading an import task status", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "processing", running_list: [], done_list: [], durations: {} }), {
        headers: { "content-type": "application/json" },
      }),
    );

    await printCareApi.getImportStatus("task k1", "test-admin-key");

    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/admin/status/task%20k1");
    expect(new Headers(request?.headers).get("X-PrintCare-Admin-Key")).toBe("test-admin-key");
  });
});
