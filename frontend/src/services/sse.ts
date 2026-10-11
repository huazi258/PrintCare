import type {
  DeltaEvent,
  DiagnosisSession,
  FinalEvent,
  ProgressEvent,
  TaskErrorEvent,
} from "@/types/api";

type EventHandler<T> = (payload: T) => void;

export interface TaskStreamHandlers {
  onProgress?: EventHandler<ProgressEvent>;
  onDelta?: EventHandler<DeltaEvent>;
  onDiagnosis?: EventHandler<DiagnosisSession>;
  onFinal?: EventHandler<FinalEvent>;
  onTaskError?: EventHandler<TaskErrorEvent>;
  onNetworkError?: EventHandler<Error>;
  onParseError?: EventHandler<Error>;
}

export interface TaskStreamSubscription {
  close: () => void;
}

export type EventSourceFactory = (url: string) => EventSource;

const defaultEventSourceFactory: EventSourceFactory = (url) => new EventSource(url);

function parseJson<T>(event: MessageEvent<string>, onParseError?: EventHandler<Error>) {
  try {
    return JSON.parse(event.data) as T;
  } catch {
    onParseError?.(new Error("服务端返回了无法解析的 SSE 数据。"));
    return undefined;
  }
}

function hasMessageData(event: Event): event is MessageEvent<string> {
  return "data" in event && typeof (event as MessageEvent<unknown>).data === "string";
}

/**
 * Connect to a core-service task stream. The URL is same-origin, so browser
 * EventSource sends the anonymous visitor cookie through Vite's proxy.
 */
export function subscribeToTask(
  taskId: string,
  handlers: TaskStreamHandlers,
  eventSourceFactory: EventSourceFactory = defaultEventSourceFactory,
): TaskStreamSubscription {
  const source = eventSourceFactory(`/api/core/stream/${encodeURIComponent(taskId)}`);
  let closed = false;

  const close = () => {
    if (!closed) {
      closed = true;
      source.close();
    }
  };

  const listen = <T>(eventName: string, handler: EventHandler<T> | undefined) => {
    if (!handler) return;
    source.addEventListener(eventName, (event) => {
      const payload = parseJson<T>(event as MessageEvent<string>, handlers.onParseError);
      if (payload !== undefined) handler(payload);
    });
  };

  listen("progress", handlers.onProgress);
  listen("delta", handlers.onDelta);
  listen("diagnosis", handlers.onDiagnosis);
  listen("final", (payload: FinalEvent) => {
    handlers.onFinal?.(payload);
    close();
  });
  listen("error", handlers.onTaskError);

  source.onerror = (event) => {
    if (closed || hasMessageData(event)) return;
    close();
    handlers.onNetworkError?.(new Error("SSE 连接意外中断。请通过任务状态或诊断详情恢复结果。"));
  };

  return { close };
}
