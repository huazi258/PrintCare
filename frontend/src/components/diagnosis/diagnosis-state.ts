import type {
  DiagnosisAnswerInput,
  DiagnosisDecision,
  DiagnosisQuestion,
  DiagnosisStatus,
} from "@/types/api";

export const MAX_CLARIFICATION_ROUNDS = 3;

export type DiagnosisSelection = {
  optionId: string;
  supplementalNote?: string;
};

export type DiagnosisSelections = Record<string, DiagnosisSelection | undefined>;

export function clampDiagnosisRound(round: number): number {
  return Math.min(Math.max(round, 1), MAX_CLARIFICATION_ROUNDS);
}

export function buildDiagnosisAnswerInputs(
  questions: DiagnosisQuestion[],
  selections: DiagnosisSelections,
): DiagnosisAnswerInput[] | null {
  const answers: DiagnosisAnswerInput[] = [];

  for (const question of questions) {
    const selection = selections[question.question_id];
    if (!selection?.optionId) {
      return null;
    }

    const option = question.options.find(
      (candidate) => candidate.option_id === selection.optionId,
    );
    if (!option) {
      return null;
    }

    const supplementalNote = selection.supplementalNote?.trim();
    answers.push({
      question_id: question.question_id,
      option_id: option.option_id,
      ...(supplementalNote ? { supplemental_note: supplementalNote } : {}),
    });
  }

  return answers;
}

export function canSubmitDiagnosisRound(
  questions: DiagnosisQuestion[],
  selections: DiagnosisSelections,
  isProcessing: boolean,
): boolean {
  return !isProcessing && buildDiagnosisAnswerInputs(questions, selections) !== null;
}

export function getDiagnosisResultKind(decision: DiagnosisDecision): "answer" | "insufficient" | null {
  return decision.action === "answer" || decision.action === "insufficient"
    ? decision.action
    : null;
}

export function isResolvedDiagnosisStatus(status: DiagnosisStatus): boolean {
  return status === "resolved";
}
