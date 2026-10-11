import { BookOpenText, Printer } from "lucide-react";

const suggestedQuestions = [
  "K1 如何进行首次打印？",
  "打印第一层无法附着怎么办？",
  "如何更换打印材料？",
];

interface QaWelcomeProps {
  onSuggestion: (question: string) => void;
}

export function QaWelcome({ onSuggestion }: QaWelcomeProps) {
  return (
    <section aria-labelledby="qa-welcome-title" className="py-8 text-center sm:py-14">
      <span className="mx-auto flex size-12 items-center justify-center rounded-xl bg-muted text-primary">
        <BookOpenText aria-hidden="true" size={24} strokeWidth={1.7} />
      </span>
      <h1 id="qa-welcome-title" className="mt-5 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
        知识问答
      </h1>
      <p className="mt-3 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1"><Printer aria-hidden="true" size={14} />当前支持设备：Creality K1</span>
      </p>
      <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-muted-foreground">
        输入与 K1 使用、参数或维护相关的问题。回答将基于已导入的设备资料，并在可用时显示来源依据。
      </p>

      <div className="mx-auto mt-8 max-w-2xl text-left">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">常见问题</p>
        <div className="flex flex-wrap justify-center gap-2">
          {suggestedQuestions.map((question) => (
            <button
              className="rounded-full border border-border bg-card px-3 py-2 text-sm text-muted-foreground outline-none transition-colors hover:border-primary/40 hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
              key={question}
              onClick={() => onSuggestion(question)}
              type="button"
            >
              {question}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
