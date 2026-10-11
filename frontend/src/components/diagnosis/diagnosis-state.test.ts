import { describe, expect, it } from "vitest";

import type { DiagnosisAskDecision, DiagnosisDecision, DiagnosisQuestion } from "@/types/api";

import {
  buildDiagnosisAnswerInputs,
  canSubmitDiagnosisRound,
  clampDiagnosisRound,
  getDiagnosisResultKind,
  isResolvedDiagnosisStatus,
} from "./diagnosis-state";

const questions: DiagnosisQuestion[] = [
  {
    question_id: "q-normal",
    text: "普通选项问题",
    options: [
      { option_id: "normal", text: "普通", option_type: "normal" },
      { option_id: "uncertain", text: "不确定", option_type: "uncertain" },
    ],
    references: [],
  },
  {
    question_id: "q-other",
    text: "其他选项问题",
    options: [
      { option_id: "other", text: "其他", option_type: "other" },
      { option_id: "normal-2", text: "普通", option_type: "normal" },
    ],
    references: [],
  },
  {
    question_id: "q-uncertain",
    text: "不确定选项问题",
    options: [
      { option_id: "uncertain-2", text: "不确定", option_type: "uncertain" },
      { option_id: "normal-3", text: "普通", option_type: "normal" },
    ],
    references: [],
  },
];

describe("diagnosis UI state helpers", () => {
  it("builds same-round DiagnosisAnswerInput values for dynamically sized 1–3 question groups", () => {
    expect(buildDiagnosisAnswerInputs(questions.slice(0, 1), { "q-normal": { optionId: "normal" } })).toEqual([
      { question_id: "q-normal", option_id: "normal" },
    ]);
    expect(buildDiagnosisAnswerInputs(questions.slice(0, 2), {
      "q-normal": { optionId: "uncertain" },
      "q-other": { optionId: "other", supplementalNote: "  机器已放置一段时间  " },
    })).toEqual([
      { question_id: "q-normal", option_id: "uncertain" },
      { question_id: "q-other", option_id: "other", supplemental_note: "机器已放置一段时间" },
    ]);
    expect(buildDiagnosisAnswerInputs(questions, {
      "q-normal": { optionId: "normal" },
      "q-other": { optionId: "other" },
      "q-uncertain": { optionId: "uncertain-2" },
    })).toHaveLength(3);
  });

  it("requires every dynamic question and blocks repeat submission while processing", () => {
    const selections = { "q-normal": { optionId: "normal" } };
    expect(buildDiagnosisAnswerInputs(questions.slice(0, 2), selections)).toBeNull();
    expect(canSubmitDiagnosisRound(questions.slice(0, 1), selections, false)).toBe(true);
    expect(canSubmitDiagnosisRound(questions.slice(0, 1), selections, true)).toBe(false);
  });

  it("keeps progress within the three-round boundary", () => {
    expect(clampDiagnosisRound(0)).toBe(1);
    expect(clampDiagnosisRound(2)).toBe(2);
    expect(clampDiagnosisRound(99)).toBe(3);
  });

  it("keeps answer and insufficient result layouts distinct", () => {
    const answer: DiagnosisDecision = {
      action: "answer",
      conclusion: "测试结论",
      conclusion_evidence: [],
      recommendations: [],
      references: [],
      safety_notes: [],
    };
    const insufficient: DiagnosisDecision = {
      action: "insufficient",
      reason: "资料不足",
      confirmed_facts: [],
      next_steps: [],
    };
    expect(getDiagnosisResultKind(answer)).toBe("answer");
    expect(getDiagnosisResultKind(insufficient)).toBe("insufficient");
  });

  it("does not treat pending verification as resolved", () => {
    expect(isResolvedDiagnosisStatus("pending_verification")).toBe(false);
    expect(isResolvedDiagnosisStatus("resolved")).toBe(true);
  });

  it("does not require optional reference excerpts in ask data", () => {
    const ask: DiagnosisAskDecision = {
      action: "ask",
      questions: [{ ...questions[0], references: [] }],
    };
    expect(() => buildDiagnosisAnswerInputs(ask.questions, { "q-normal": { optionId: "normal" } })).not.toThrow();
  });
});
