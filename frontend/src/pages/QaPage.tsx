import { useEffect, useMemo, useRef, useState } from "react";
import { MessageSquarePlus, Printer, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConversationMessage } from "@/components/qa/ConversationMessage";
import { QaPreviewControls } from "@/components/qa/QaPreviewControls";
import { QaWelcome } from "@/components/qa/QaWelcome";
import { QuestionComposer } from "@/components/qa/QuestionComposer";
import {
  appendAssistantDelta,
  buildQaRequest,
  historyToQaMessages,
  QA_SESSION_STORAGE_KEY,
  replaceAssistantAnswer,
} from "@/components/qa/qa-session";
import { PageContainer } from "@/components/PageContainer";
import { printCareApi } from "@/services/printcare-api";
import { subscribeToTask, type TaskStreamSubscription } from "@/services/sse";
import type { ProgressEvent } from "@/types/api";
import type { QaMessage } from "@/types/qa";

export type QaPreviewState = "welcome" | "generating" | "complete" | "error" | "no-sources";

const previewQuestion = "打印第一层无法附着怎么办？";

const previewAnswer = `## 首层附着排查思路

可以先从打印平台表面状态与首层参数开始检查：

1. 确认打印平台上没有残留物、油污或旧的胶水痕迹。
2. 检查模型切片中的首层速度与首层高度设置。
3. 若需要调整参数，请一次只修改一个因素，再观察打印结果。

> 涉及热端、高温平台或拆机操作时，应以实际资料中的安全提示为准。

可将当前材料、平台处理方式和首层现象补充到下一轮问题中。示例参数如 \`首层速度\` 应结合所用材料确认。`;

const previewSources = [
  {
    title: "模拟本地资料（开发预览）",
    type: "local" as const,
    detail: "仅用于验证来源组件的展开样式，不对应真实设备文档或知识库切片。",
  },
  {
    title: "模拟联网来源（开发预览）",
    type: "web" as const,
    detail: "仅用于验证来源类型标签，不表示诊断或问答已经执行联网检索。",
  },
];

const STATUS_FALLBACK_DELAY_MS = 4000;
const STATUS_FALLBACK_MAX_ATTEMPTS = 3;

function buildPreviewMessages(state: QaPreviewState): QaMessage[] {
  if (state === "welcome") return [];
  const messages: QaMessage[] = [{ id: "preview-user", role: "user", content: previewQuestion }];
  if (state !== "error") {
    messages.push({
      id: "preview-assistant",
      role: "assistant",
      content: state === "generating" ? "" : previewAnswer,
      sources: state === "complete" ? previewSources : [],
    });
  }
  return messages;
}

export function QaPage() {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const previewParameter = new URLSearchParams(window.location.search).get("preview");
  const isPreview = import.meta.env.DEV && ["welcome", "generating", "complete", "error", "no-sources"].includes(previewParameter ?? "");
  const initialPreviewState = (isPreview ? previewParameter : "welcome") as QaPreviewState;
  const [previewState, setPreviewState] = useState<QaPreviewState>(initialPreviewState);
  const [draft, setDraft] = useState("");
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [liveMessages, setLiveMessages] = useState<QaMessage[]>([]);
  const [isRestoring, setIsRestoring] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [progressMessage, setProgressMessage] = useState<string | null>(null);
  const streamRef = useRef<TaskStreamSubscription | null>(null);
  const requestAbortRef = useRef<AbortController | null>(null);
  const activeTaskIdRef = useRef<string | null>(null);
  const statusFallbackTimerRef = useRef<ReturnType<typeof window.setTimeout> | null>(null);
  const statusFallbackAttemptsRef = useRef(0);
  const mountedRef = useRef(true);
  const messageSequenceRef = useRef(0);
  const messages = useMemo(() => (isPreview ? buildPreviewMessages(previewState) : liveMessages), [isPreview, liveMessages, previewState]);
  const isGenerating = isPreview ? previewState === "generating" : isSubmitting;

  const focusComposer = () => requestAnimationFrame(() => textareaRef.current?.focus());

  const finishTask = (taskId: string) => {
    if (activeTaskIdRef.current !== taskId) return false;
    if (statusFallbackTimerRef.current !== null) {
      window.clearTimeout(statusFallbackTimerRef.current);
      statusFallbackTimerRef.current = null;
    }
    activeTaskIdRef.current = null;
    streamRef.current?.close();
    streamRef.current = null;
    if (mountedRef.current) setIsSubmitting(false);
    return true;
  };

  const describeProgress = (progress: ProgressEvent) => {
    if (progress.message?.trim()) return progress.message;
    const running = progress.running_list?.at(-1);
    if (running) return `正在${running}`;
    const completed = progress.done_list?.at(-1);
    if (completed) return `已完成${completed}`;
    return "正在基于设备资料生成回答…";
  };

  const recoverTask = async (
    taskId: string,
    assistantMessageId: string,
    reportUnavailable = true,
  ) => {
    try {
      const status = await printCareApi.getQueryStatus(taskId);
      if (!mountedRef.current || activeTaskIdRef.current !== taskId) return true;
      if (status.answer) {
        setLiveMessages((current) => replaceAssistantAnswer(current, assistantMessageId, status.answer));
        setStatusNotice("已通过任务状态恢复完整回答。");
        setSubmissionError(null);
        finishTask(taskId);
        return true;
      } else if (status.error) {
        setSubmissionError(status.error);
        finishTask(taskId);
        return true;
      } else {
        if (reportUnavailable) {
          setSubmissionError("SSE 连接中断，任务状态尚未返回完整回答。请稍后刷新页面或重新提问。");
          finishTask(taskId);
          return true;
        }
        return false;
      }
    } catch {
      if (reportUnavailable && mountedRef.current && activeTaskIdRef.current === taskId) {
        setSubmissionError("SSE 连接中断，且暂时无法读取任务状态。请稍后重试。");
        finishTask(taskId);
        return true;
      }
      return false;
    }
  };

  const scheduleStatusFallback = (
    taskId: string,
    assistantMessageId: string,
    resetAttempts = true,
  ) => {
    if (statusFallbackTimerRef.current !== null) {
      window.clearTimeout(statusFallbackTimerRef.current);
    }
    if (resetAttempts) statusFallbackAttemptsRef.current = 0;
    statusFallbackTimerRef.current = window.setTimeout(async () => {
      statusFallbackTimerRef.current = null;
      if (activeTaskIdRef.current === taskId) {
        const finished = await recoverTask(taskId, assistantMessageId, false);
        if (
          !finished
          && activeTaskIdRef.current === taskId
          && statusFallbackAttemptsRef.current < STATUS_FALLBACK_MAX_ATTEMPTS
        ) {
          statusFallbackAttemptsRef.current += 1;
          scheduleStatusFallback(taskId, assistantMessageId, false);
        }
      }
    }, STATUS_FALLBACK_DELAY_MS);
  };

  useEffect(() => {
    if (isPreview) return;
    const storedSessionId = window.localStorage.getItem(QA_SESSION_STORAGE_KEY);
    if (!storedSessionId) return;

    const controller = new AbortController();
    setSessionId(storedSessionId);
    setIsRestoring(true);
    printCareApi.getQueryHistory(storedSessionId, { signal: controller.signal })
      .then((history) => {
        if (mountedRef.current) setLiveMessages(historyToQaMessages(history.items));
      })
      .catch(() => {
        if (!controller.signal.aborted && mountedRef.current) {
          setSubmissionError("当前会话历史暂时无法读取；你仍可继续提问。");
        }
      })
      .finally(() => {
        if (mountedRef.current) setIsRestoring(false);
      });

    return () => controller.abort();
  }, [isPreview]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestAbortRef.current?.abort();
      streamRef.current?.close();
      if (statusFallbackTimerRef.current !== null) window.clearTimeout(statusFallbackTimerRef.current);
    };
  }, []);

  const handleSuggestion = (question: string) => {
    setDraft(question);
    setSubmissionError(null);
    focusComposer();
  };

  const handleSubmit = async () => {
    const query = draft.trim();
    if (!query || isPreview || isSubmitting) return;

    const assistantMessageId = `assistant-${Date.now()}-${messageSequenceRef.current++}`;
    const userMessageId = `user-${Date.now()}-${messageSequenceRef.current++}`;
    const controller = new AbortController();
    let taskId: string | null = null;
    requestAbortRef.current = controller;
    setDraft("");
    setSubmissionError(null);
    setStatusNotice(null);
    setProgressMessage("正在提交问题…");
    setIsSubmitting(true);
    setLiveMessages((current) => [
      ...current,
      { id: userMessageId, role: "user", content: query },
      { id: assistantMessageId, role: "assistant", content: "" },
    ]);

    try {
      const response = await printCareApi.submitQuery(buildQaRequest(query, sessionId ?? undefined), {
        signal: controller.signal,
      });
      if (!response.task_id) throw new Error("问答服务未返回任务标识。");
      if (typeof response.session_id === "string" && response.session_id) {
        setSessionId(response.session_id);
        window.localStorage.setItem(QA_SESSION_STORAGE_KEY, response.session_id);
      }

      const startedTaskId = response.task_id;
      taskId = startedTaskId;
      activeTaskIdRef.current = startedTaskId;
      streamRef.current = subscribeToTask(startedTaskId, {
        onProgress: (progress) => {
          if (activeTaskIdRef.current === startedTaskId) setProgressMessage(describeProgress(progress));
        },
        onDelta: ({ delta }) => {
          if (activeTaskIdRef.current === startedTaskId) {
            setLiveMessages((current) => appendAssistantDelta(current, assistantMessageId, delta));
            scheduleStatusFallback(startedTaskId, assistantMessageId);
          }
        },
        onFinal: ({ answer }) => {
          if (!finishTask(startedTaskId)) return;
          if (answer) {
            setLiveMessages((current) => replaceAssistantAnswer(current, assistantMessageId, answer));
          }
          setProgressMessage(null);
        },
        onTaskError: ({ message }) => {
          streamRef.current?.close();
          if (!finishTask(startedTaskId)) return;
          setSubmissionError(message || "问答任务失败，请稍后重试。");
          setProgressMessage(null);
        },
        onNetworkError: () => {
          void recoverTask(startedTaskId, assistantMessageId);
        },
        onParseError: () => {
          if (activeTaskIdRef.current === startedTaskId) {
            setSubmissionError("服务端返回了无法解析的流式数据，正在等待后续结果。");
          }
        },
      });
    } catch (error) {
      if (controller.signal.aborted) return;
      if (taskId && activeTaskIdRef.current === taskId) {
        streamRef.current?.close();
        activeTaskIdRef.current = null;
      }
      setLiveMessages((current) => current.filter((message) => message.id !== assistantMessageId && message.id !== userMessageId));
      setDraft(query);
      setSubmissionError(error instanceof Error ? error.message : "提交问答请求失败，请稍后重试。");
      setProgressMessage(null);
      setIsSubmitting(false);
    } finally {
      if (requestAbortRef.current === controller) requestAbortRef.current = null;
    }
  };

  const handleCopy = async () => {
    const answer = [...messages].reverse().find((message) => message.role === "assistant")?.content;
    if (!answer) return;
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
    } catch {
      setSubmissionError("当前浏览器无法复制内容，请手动选择回答文本。");
    }
  };

  const handleNewConversation = () => {
    if (!isPreview) {
      requestAbortRef.current?.abort();
      streamRef.current?.close();
      activeTaskIdRef.current = null;
      window.localStorage.removeItem(QA_SESSION_STORAGE_KEY);
      setSessionId(null);
      setLiveMessages([]);
      setIsSubmitting(false);
      setProgressMessage(null);
      setStatusNotice(null);
    }
    setPreviewState("welcome");
    setDraft("");
    setSubmissionError(null);
    setCopied(false);
    focusComposer();
  };

  return (
    <PageContainer className="max-w-[800px]">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="flex items-center gap-1.5 text-sm font-medium text-primary"><Printer aria-hidden="true" size={15} />Creality K1</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">知识问答</h1>
        </div>
        <Button onClick={handleNewConversation} size="sm" type="button" variant="outline">
          <MessageSquarePlus aria-hidden="true" size={15} />
          新建问答
        </Button>
      </header>

      {isPreview && <QaPreviewControls onChange={setPreviewState} state={previewState} />}

      {isRestoring ? (
        <p aria-live="polite" className="mt-8 flex items-center gap-2 text-sm text-muted-foreground">正在恢复当前会话历史…</p>
      ) : messages.length === 0 ? (
        <QaWelcome onSuggestion={handleSuggestion} />
      ) : (
        <section aria-label="问答阅读区" className="mt-9">
          {isPreview && <p className="mb-5 inline-flex rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">开发预览（模拟数据，不来自知识库）</p>}
          {messages.map((message) => (
            <ConversationMessage
              isGenerating={isGenerating && message.role === "assistant"}
              key={message.id}
              message={message}
              onCopy={message.role === "assistant" ? handleCopy : undefined}
            />
          ))}
          {isPreview && previewState === "error" && (
            <div aria-live="assertive" className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              模拟请求失败：当前仅验证错误状态，未调用真实问答服务。
            </div>
          )}
          {copied && (
            <p aria-live="polite" className="mt-3 flex items-center justify-between rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
              已复制模拟回答文本。
              <button aria-label="关闭复制提示" className="ml-2 outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setCopied(false)} type="button"><X aria-hidden="true" size={14} /></button>
            </p>
          )}
        </section>
      )}

      {submissionError && (
        <div aria-live="assertive" className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {submissionError}
        </div>
      )}
      {statusNotice && (
        <p aria-live="polite" className="mb-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary">{statusNotice}</p>
      )}
      <div className="sticky bottom-0 -mx-4 mt-6 bg-background/95 px-4 pb-2 pt-4 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10">
        {progressMessage && !isPreview && <p aria-live="polite" className="mb-2 px-1 text-xs text-muted-foreground">{progressMessage}</p>}
        <QuestionComposer
          isSubmitting={isGenerating}
          onChange={(value) => {
            setDraft(value);
            setSubmissionError(null);
          }}
          onSubmit={handleSubmit}
          textareaRef={textareaRef}
          value={draft}
        />
      </div>
    </PageContainer>
  );
}
