import { describe, expect, it } from "vitest";
import {
  appendAssistantDelta,
  buildQaRequest,
  historyToQaMessages,
  parseQaSessionIndex,
  qaSourcesFromReferences,
  removeQaSessionIndex,
  replaceAssistantAnswer,
  upsertQaSessionIndex,
} from "./qa-session";

describe("QA 会话状态辅助函数", () => {
  it("builds the scoped streaming K1 request", () => {
    expect(buildQaRequest("首层无法附着", "session-1")).toEqual({
      query: "首层无法附着",
      session_id: "session-1",
      is_stream: true,
      device_id: "creality-k1",
      mode: "qa",
    });
  });

  it("maps history sources without inventing metadata for old records", () => {
    expect(historyToQaMessages([
      { _id: "1", session_id: "s", role: "user", text: "问题", rewritten_query: "", item_names: [], ts: 1 },
      {
        _id: "2", session_id: "s", role: "assistant", text: "回答", rewritten_query: "", item_names: [], ts: 2,
        sources: [{
          source_type: "local", source_id: "chunk:101", title: "Creality K1 用户手册",
          section_title: "调平", excerpt: "热床调平说明",
        }],
      },
      { _id: "3", session_id: "s", role: "system", text: "忽略", rewritten_query: "", item_names: [], ts: 3 },
      { _id: "4", session_id: "s", role: "assistant", text: "  ", rewritten_query: "", item_names: [], ts: 4 },
    ])).toEqual([
      { id: "1", role: "user", content: "问题" },
      {
        id: "2", role: "assistant", content: "回答", sources: [{
          sourceId: "chunk:101", type: "local", title: "Creality K1 用户手册",
          sectionTitle: "调平", excerpt: "热床调平说明",
        }],
      },
    ]);
  });

  it("keeps only traceable local and web source fields", () => {
    expect(qaSourcesFromReferences([
      {
        source_type: "web", source_id: "https://example.test/k1", title: null,
        excerpt: "网页资料", url: "https://example.test/k1",
      },
      { source_type: "local", source_id: "", excerpt: "missing id" },
    ])).toEqual([{
      sourceId: "https://example.test/k1",
      type: "web",
      excerpt: "网页资料",
      href: "https://example.test/k1",
    }]);
  });

  it("appends deltas and replaces them with the final answer without duplication", () => {
    const initial = [
      { id: "user", role: "user" as const, content: "问题" },
      { id: "assistant", role: "assistant" as const, content: "" },
    ];
    const streaming = appendAssistantDelta(initial, "assistant", "第一段");
    const completed = replaceAssistantAnswer(streaming, "assistant", "完整回答", [{
      sourceId: "chunk:101",
      type: "local",
      excerpt: "K1 手册片段",
    }]);

    expect(streaming[1].content).toBe("第一段");
    expect(completed[1].content).toBe("完整回答");
    expect(completed[1].sources).toEqual([{ sourceId: "chunk:101", type: "local", excerpt: "K1 手册片段" }]);
  });

  it("keeps a browser-local QA session index without claiming it is a server list", () => {
    const indexed = upsertQaSessionIndex([], "session-a", 10);
    const refreshed = upsertQaSessionIndex(indexed, "session-a", 20);
    const second = upsertQaSessionIndex(refreshed, "session-b", 30);

    expect(second).toEqual([
      { sessionId: "session-b", createdAt: 30, updatedAt: 30 },
      { sessionId: "session-a", createdAt: 10, updatedAt: 20 },
    ]);
    expect(parseQaSessionIndex(JSON.stringify(second))).toEqual(second);
    expect(parseQaSessionIndex("not-json")).toEqual([]);
    expect(removeQaSessionIndex(second, "session-a")).toEqual([{ sessionId: "session-b", createdAt: 30, updatedAt: 30 }]);
  });
});
