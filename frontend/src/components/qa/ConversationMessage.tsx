import { Bot, UserRound } from "lucide-react";
import { AnswerContent } from "@/components/qa/AnswerContent";
import { SourceReferences } from "@/components/qa/SourceReferences";
import type { QaMessage } from "@/types/qa";

interface ConversationMessageProps {
  message: QaMessage;
  isGenerating?: boolean;
  onCopy?: () => void;
}

export function ConversationMessage({ message, isGenerating, onCopy }: ConversationMessageProps) {
  const isAssistant = message.role === "assistant";
  return (
    <article className="border-b border-border py-7 first:pt-0 last:border-b-0">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <span className="flex size-7 items-center justify-center rounded-full bg-muted text-primary">
          {isAssistant ? <Bot aria-hidden="true" size={15} /> : <UserRound aria-hidden="true" size={15} />}
        </span>
        {isAssistant ? "PrintCare AI" : "你"}
      </div>
      <div className="mt-4 pl-0 sm:pl-9">
        {isAssistant ? <AnswerContent content={message.content} isGenerating={isGenerating} onCopy={isGenerating ? undefined : onCopy} /> : <p className="whitespace-pre-wrap text-base leading-7 text-foreground">{message.content}</p>}
        {isAssistant && !isGenerating && <SourceReferences sources={message.sources} />}
      </div>
    </article>
  );
}
