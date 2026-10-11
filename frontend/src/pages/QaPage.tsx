import { useMemo, useRef, useState } from "react";
import { MessageSquarePlus, Printer, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConversationMessage } from "@/components/qa/ConversationMessage";
import { QaPreviewControls } from "@/components/qa/QaPreviewControls";
import { QaWelcome } from "@/components/qa/QaWelcome";
import { QuestionComposer } from "@/components/qa/QuestionComposer";
import { PageContainer } from "@/components/PageContainer";
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
  const initialPreviewState: QaPreviewState = import.meta.env.DEV && new URLSearchParams(window.location.search).get("preview") === "complete" ? "complete" : "welcome";
  const [previewState, setPreviewState] = useState<QaPreviewState>(initialPreviewState);
  const [draft, setDraft] = useState("");
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const isPreview = import.meta.env.DEV;
  const messages = useMemo(() => (isPreview ? buildPreviewMessages(previewState) : []), [isPreview, previewState]);
  const isGenerating = isPreview && previewState === "generating";

  const focusComposer = () => requestAnimationFrame(() => textareaRef.current?.focus());

  const handleSuggestion = (question: string) => {
    setDraft(question);
    setSubmissionError(null);
    focusComposer();
  };

  const handleSubmit = () => {
    setSubmissionError("问答服务尚待联调，内容已保留在输入框中，尚未发送到后端。");
  };

  const handleCopy = async () => {
    const answer = messages.find((message) => message.role === "assistant")?.content;
    if (!answer) return;
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
    } catch {
      setSubmissionError("当前浏览器无法复制内容，请手动选择回答文本。");
    }
  };

  const handleNewConversation = () => {
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

      {previewState === "welcome" ? (
        <QaWelcome onSuggestion={handleSuggestion} />
      ) : (
        <section aria-label="问答阅读区" className="mt-9">
          <p className="mb-5 inline-flex rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">开发预览（模拟数据，不来自知识库）</p>
          {messages.map((message) => (
            <ConversationMessage
              isGenerating={isGenerating && message.role === "assistant"}
              key={message.id}
              message={message}
              onCopy={message.role === "assistant" ? handleCopy : undefined}
            />
          ))}
          {previewState === "error" && (
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
      <div className="sticky bottom-0 -mx-4 mt-6 bg-background/95 px-4 pb-2 pt-4 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10">
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
