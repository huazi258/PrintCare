import { Copy, LoaderCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";

interface AnswerContentProps {
  content?: string;
  isGenerating?: boolean;
  onCopy?: () => void;
}

export function AnswerContent({ content, isGenerating = false, onCopy }: AnswerContentProps) {
  if (isGenerating) {
    return (
      <div aria-live="polite" className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
        <LoaderCircle aria-hidden="true" className="animate-spin text-primary" size={17} />
        正在基于设备资料生成回答…
      </div>
    );
  }

  if (!content) return null;

  return (
    <div className="group relative">
      {onCopy && (
        <Button
          aria-label="复制回答"
          className="absolute right-0 top-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100"
          onClick={onCopy}
          size="sm"
          type="button"
          variant="ghost"
        >
          <Copy aria-hidden="true" size={15} />
          复制
        </Button>
      )}
      <div className="qa-markdown pr-0 sm:pr-16">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h2: ({ children }) => <h2>{children}</h2>,
            h3: ({ children }) => <h3>{children}</h3>,
            a: ({ href, children }) => <a href={href} rel="noreferrer" target="_blank">{children}</a>,
            code: ({ className, children, ...props }) => {
              const isBlock = className?.includes("language-");
              return isBlock ? <code className={className} {...props}>{children}</code> : <code {...props}>{children}</code>;
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
