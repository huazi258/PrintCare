import { describe, expect, it } from "vitest";
import {
  appendAssistantDelta,
  buildQaRequest,
  historyToQaMessages,
  replaceAssistantAnswer,
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

  it("maps only supported, non-empty history messages without inventing sources", () => {
    expect(historyToQaMessages([
      { _id: "1", session_id: "s", role: "user", text: "问题", rewritten_query: "", item_names: [], ts: 1 },
      { _id: "2", session_id: "s", role: "assistant", text: "回答", rewritten_query: "", item_names: [], ts: 2 },
      { _id: "3", session_id: "s", role: "system", text: "忽略", rewritten_query: "", item_names: [], ts: 3 },
      { _id: "4", session_id: "s", role: "assistant", text: "  ", rewritten_query: "", item_names: [], ts: 4 },
    ])).toEqual([
      { id: "1", role: "user", content: "问题" },
      { id: "2", role: "assistant", content: "回答" },
    ]);
  });

  it("appends deltas and replaces them with the final answer without duplication", () => {
    const initial = [
      { id: "user", role: "user" as const, content: "问题" },
      { id: "assistant", role: "assistant" as const, content: "" },
    ];
    const streaming = appendAssistantDelta(initial, "assistant", "第一段");
    const completed = replaceAssistantAnswer(streaming, "assistant", "完整回答");

    expect(streaming[1].content).toBe("第一段");
    expect(completed[1].content).toBe("完整回答");
  });
});
