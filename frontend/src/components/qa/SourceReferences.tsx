import { BookOpen, ChevronDown, Globe2 } from "lucide-react";
import type { QaSource } from "@/types/qa";

interface SourceReferencesProps {
  sources?: QaSource[];
}

export function SourceReferences({ sources }: SourceReferencesProps) {
  if (!sources || sources.length === 0) {
    return <p className="mt-5 border-t border-border pt-4 text-xs text-muted-foreground">本次回答暂未提供可展示来源。</p>;
  }

  return (
    <section aria-label="回答来源" className="mt-6 border-t border-border pt-4">
      <h3 className="text-sm font-medium text-foreground">本轮回答参考来源</h3>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">仅列出本轮生成时实际进入上下文的资料片段，不表示逐句引用或逐项验证。</p>
      <div className="mt-3 space-y-2">
        {sources.map((source) => {
          const Icon = source.type === "local" ? BookOpen : Globe2;
          const typeLabel = source.type === "local" ? "本地资料" : "联网来源";
          return (
            <details className="group rounded-lg border border-border bg-card" key={`${source.type}-${source.sourceId}`}>
              <summary className="flex cursor-pointer list-none items-center gap-3 px-3 py-2.5 outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground"><Icon aria-hidden="true" size={15} /></span>
                <span className="min-w-0 flex-1 truncate text-sm text-foreground">{source.title || source.sourceId}</span>
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{typeLabel}</span>
                <ChevronDown aria-hidden="true" className="shrink-0 text-muted-foreground transition-transform group-open:rotate-180" size={16} />
              </summary>
              <div className="border-t border-border px-3 py-3 text-sm leading-6 text-muted-foreground">
                <p className="break-all text-xs text-muted-foreground">来源标识：{source.sourceId}</p>
                {source.sectionTitle && <p className="mt-2">章节：{source.sectionTitle}</p>}
                {source.excerpt && <p className="mt-2 whitespace-pre-wrap">{source.excerpt}</p>}
                {source.href && <a className="mt-2 inline-block text-primary underline underline-offset-2" href={source.href} rel="noreferrer" target="_blank">打开来源</a>}
              </div>
            </details>
          );
        })}
      </div>
    </section>
  );
}
