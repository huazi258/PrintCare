import { Check } from "lucide-react";

import { clampDiagnosisRound, MAX_CLARIFICATION_ROUNDS } from "./diagnosis-state";

type DiagnosisProgressProps = {
  round: number;
  stage: "questions" | "result";
};

const steps = ["描述问题", "补充信息", "查看结果"];

export function DiagnosisProgress({ round, stage }: DiagnosisProgressProps) {
  const displayRound = clampDiagnosisRound(round);
  const activeStep = stage === "result" ? 3 : Math.min(displayRound + 1, 2);

  return (
    <div>
      <p className="text-sm font-medium text-primary">
        第 {displayRound} 轮 / 最多 {MAX_CLARIFICATION_ROUNDS} 轮
      </p>
      <ol className="mt-3 grid grid-cols-3 gap-2" aria-label="诊断进度">
        {steps.map((step, index) => {
          const stepNumber = index + 1;
          const isCurrent = stepNumber === activeStep;
          const isComplete = stepNumber < activeStep;

          return (
            <li key={step} className="min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className={`flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                    isCurrent || isComplete
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  }`}
                  aria-hidden="true"
                >
                  {isComplete ? <Check className="size-3.5" /> : stepNumber}
                </span>
                <span className={`truncate text-xs sm:text-sm ${isCurrent ? "font-medium text-foreground" : "text-muted-foreground"}`}>
                  {step}
                </span>
              </div>
              <div className={`mt-2 h-1 rounded-full ${isCurrent || isComplete ? "bg-primary" : "bg-muted"}`} />
            </li>
          );
        })}
      </ol>
    </div>
  );
}
