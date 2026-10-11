import type { KeyboardEvent, RefObject } from "react";
import { CornerDownLeft, LoaderCircle, Send } from "lucide-react";
import { Button } from "@/components/ui/button";

interface QuestionComposerProps {
  value: string;
  isSubmitting: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
  textareaRef?: RefObject<HTMLTextAreaElement | null>;
}

export function QuestionComposer({
  value,
  isSubmitting,
  onChange,
  onSubmit,
  textareaRef,
}: QuestionComposerProps) {
  const canSubmit = value.trim().length > 0 && !isSubmitting;

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSubmit) onSubmit();
    }
  };

  return (
    <form
      aria-label="知识问答输入"
      className="rounded-xl border border-border bg-card p-3 shadow-sm focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-ring/20"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) onSubmit();
      }}
    >
      <label className="sr-only" htmlFor="qa-question">输入 K1 相关问题</label>
      <textarea
        className="min-h-24 w-full resize-y bg-transparent px-2 py-1 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
        disabled={isSubmitting}
        id="qa-question"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="例如：K1 如何进行首次打印？"
        ref={textareaRef}
        value={value}
      />
      <div className="mt-2 flex items-center justify-between gap-3 px-1">
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <CornerDownLeft aria-hidden="true" size={13} /> Enter 发送 · Shift + Enter 换行
        </p>
        <Button disabled={!canSubmit} size="sm" type="submit">
          {isSubmitting ? <LoaderCircle aria-hidden="true" className="animate-spin" size={15} /> : <Send aria-hidden="true" size={15} />}
          {isSubmitting ? "生成中" : "发送"}
        </Button>
      </div>
    </form>
  );
}
