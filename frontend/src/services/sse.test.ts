import { describe, expect, it, vi } from "vitest";
import { subscribeToTask } from "@/services/sse";

class MockEventSource {
  public onerror: ((event: Event) => void) | null = null;
  public closed = false;
  public readonly listeners = new Map<string, Array<(event: Event) => void>>();

  public constructor(public readonly url: string) {}

  public addEventListener(type: string, listener: (event: Event) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  public close() {
    this.closed = true;
  }

  public emit(type: string, payload: unknown) {
    const event = { data: JSON.stringify(payload) } as MessageEvent<string>;
    this.listeners.get(type)?.forEach((listener) => listener(event));
  }
}

describe("subscribeToTask", () => {
  it("解析事件并在 final 后关闭连接", () => {
    let source: MockEventSource | undefined;
    const onProgress = vi.fn();
    const onDiagnosis = vi.fn();
    const onFinal = vi.fn();

    subscribeToTask(
      "task / 1",
      { onProgress, onDiagnosis, onFinal },
      (url) => {
        source = new MockEventSource(url);
        return source as unknown as EventSource;
      },
    );

    expect(source?.url).toBe("/api/core/stream/task%20%2F%201");
    source?.emit("progress", { stage: "retrieval", message: "正在检索" });
    source?.emit("diagnosis", { diagnosis_id: "d-1", status: "in_progress" });
    source?.emit("final", { status: "completed", diagnosis_id: "d-1" });

    expect(onProgress).toHaveBeenCalledWith({ stage: "retrieval", message: "正在检索" });
    expect(onDiagnosis).toHaveBeenCalledWith({ diagnosis_id: "d-1", status: "in_progress" });
    expect(onFinal).toHaveBeenCalledWith({ status: "completed", diagnosis_id: "d-1" });
    expect(source?.closed).toBe(true);
  });

  it("网络错误会关闭连接且不触发自动重连", () => {
    let source: MockEventSource | undefined;
    const onNetworkError = vi.fn();

    subscribeToTask(
      "task-2",
      { onNetworkError },
      (url) => {
        source = new MockEventSource(url);
        return source as unknown as EventSource;
      },
    );

    source?.onerror?.(new Event("error"));

    expect(source?.closed).toBe(true);
    expect(onNetworkError).toHaveBeenCalledOnce();
  });
});
