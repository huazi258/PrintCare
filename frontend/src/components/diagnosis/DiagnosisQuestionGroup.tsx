import { CircleHelp, Info, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { DiagnosisAnswerInput, DiagnosisQuestion } from "@/types/api";

import {
  buildDiagnosisAnswerInputs,
  canSubmitDiagnosisRound,
  type DiagnosisSelections,
} from "./diagnosis-state";

type DiagnosisQuestionGroupProps = {
  questions: DiagnosisQuestion[];
  selections: DiagnosisSelections;
  isProcessing: boolean;
  onSelectionChange: (questionId: string, optionId: string) => void;
  onSupplementalNoteChange: (questionId: string, note: string) => void;
  onSubmit: (answers: DiagnosisAnswerInput[]) => void;
};

export function DiagnosisQuestionGroup({
  questions,
  selections,
  isProcessing,
  onSelectionChange,
  onSupplementalNoteChange,
  onSubmit,
}: DiagnosisQuestionGroupProps) {
  const canSubmit = canSubmitDiagnosisRound(questions, selections, isProcessing);

  function handleSubmit() {
    const answers = buildDiagnosisAnswerInputs(questions, selections);
    if (answers) {
      onSubmit(answers);
    }
  }

  return (
    <section aria-labelledby="question-group-title">
      <div className="mb-5 flex gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <CircleHelp className="size-5" aria-hidden="true" />
        </div>
        <div>
          <h2 id="question-group-title" className="text-lg font-semibold text-foreground">
            请补充以下信息
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            本轮问题需要统一提交。无法确认时可选择“不确定”或“其他情况”。
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {questions.map((question, index) => {
          const selection = selections[question.question_id];
          const selectedOption = question.options.find((option) => option.option_id === selection?.optionId);
          const showSupplementalNote = selectedOption?.option_type === "other";

          return (
            <fieldset key={question.question_id} className="rounded-xl border border-border bg-card p-5 shadow-[0_2px_10px_rgba(27,36,48,0.04)]">
              <legend className="sr-only">问题 {index + 1}</legend>
              <p className="text-sm font-medium text-primary">问题 {index + 1}</p>
              <h3 className="mt-2 text-base font-semibold leading-7 text-foreground">{question.text}</h3>
              <div className="mt-4 grid gap-2">
                {question.options.map((option) => {
                  const isSelected = selection?.optionId === option.option_id;
                  const optionKind = option.option_type === "uncertain" ? "不确定" : option.option_type === "other" ? "其他" : null;

                  return (
                    <label
                      key={option.option_id}
                      className={`flex cursor-pointer items-start gap-3 rounded-[10px] border px-3 py-3 text-sm leading-6 transition focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 ${
                        isSelected ? "border-primary bg-primary/5 text-foreground" : "border-border bg-background text-foreground hover:border-primary/50"
                      }`}
                    >
                      <input
                        type="radio"
                        name={question.question_id}
                        value={option.option_id}
                        checked={isSelected}
                        onChange={() => onSelectionChange(question.question_id, option.option_id)}
                        className="mt-1 size-4 accent-primary"
                        disabled={isProcessing}
                      />
                      <span className="min-w-0 flex-1 break-words">{option.text}</span>
                      {optionKind ? (
                        <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{optionKind}</span>
                      ) : null}
                    </label>
                  );
                })}
              </div>
              {showSupplementalNote ? (
                <div className="mt-3">
                  <label htmlFor={`${question.question_id}-note`} className="text-sm font-medium text-foreground">
                    补充说明（选填）
                  </label>
                  <textarea
                    id={`${question.question_id}-note`}
                    value={selection?.supplementalNote ?? ""}
                    onChange={(event) => onSupplementalNoteChange(question.question_id, event.target.value)}
                    disabled={isProcessing}
                    rows={3}
                    placeholder="可补充具体情况，后续将与本题答案一并提交。"
                    className="mt-2 w-full resize-y rounded-lg border border-input bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </div>
              ) : null}
            </fieldset>
          );
        })}
      </div>

      <div className="sticky bottom-3 mt-6 flex flex-col gap-3 rounded-xl border border-border bg-card/95 p-4 shadow-[0_8px_24px_rgba(27,36,48,0.08)] backdrop-blur sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-start gap-2 text-sm leading-5 text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          未完成所有问题前无法提交本轮答案。
        </p>
        <Button type="button" onClick={handleSubmit} disabled={!canSubmit} className="min-w-32">
          {isProcessing ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
          {isProcessing ? "处理中…" : "提交本轮答案"}
        </Button>
      </div>
    </section>
  );
}
