import { describe, expect, it } from "vitest";

import type { DiagnosisSession } from "@/types/api";

import {
  buildDiagnosisAnswerRequest,
  buildDiagnosisStartRequest,
  buildResumeUnresolvedRequest,
  isDiagnosing,
} from "./diagnosis-session";

const session: DiagnosisSession = {
  diagnosis_id: "diagnosis-1",
  device_id: "creality-k1",
  device_model: "Creality K1",
  original_problem: "首层无法附着",
  status: "in_progress",
  clarification_round: 1,
  revision: 4,
  facts: [],
  rounds: [],
  decision: null,
  feedback: null,
  created_at: null,
  updated_at: null,
};

describe("诊断会话请求", () => {
  it("creates the scoped streaming K1 start request", () => {
    expect(buildDiagnosisStartRequest("首层无法附着", "start-1")).toEqual({
      mode: "diagnosis", is_stream: true, device_id: "creality-k1",
      original_problem: "首层无法附着", request_id: "start-1",
    });
  });

  it("submits a complete batch using the server revision", () => {
    expect(buildDiagnosisAnswerRequest(session, [{ question_id: "q1", option_id: "o1" }], "answer-1")).toEqual({
      mode: "diagnosis", is_stream: true, diagnosis_id: "diagnosis-1",
      answers: [{ question_id: "q1", option_id: "o1" }], request_id: "answer-1", expected_revision: 4,
    });
  });

  it("uses the persisted session revision when requesting an unresolved resume", () => {
    expect(buildResumeUnresolvedRequest(session, "resume-1")).toMatchObject({
      diagnosis_id: "diagnosis-1", expected_revision: 4, request_id: "resume-1", resume_unresolved: true,
    });
    expect(isDiagnosing(session)).toBe(true);
    expect(isDiagnosing({ ...session, decision: { action: "ask", questions: [] } })).toBe(false);
  });
});
