import type { DiagnosisAnswerInput, DiagnosisSession, QueryRequest } from "@/types/api";

export const DIAGNOSIS_STORAGE_KEY = "printcare.diagnosis.id";

export function createDiagnosisRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `diagnosis-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function buildDiagnosisStartRequest(problem: string, requestId: string): QueryRequest {
  return {
    mode: "diagnosis",
    is_stream: true,
    device_id: "creality-k1",
    original_problem: problem,
    request_id: requestId,
  };
}

export function buildDiagnosisAnswerRequest(
  session: DiagnosisSession,
  answers: DiagnosisAnswerInput[],
  requestId: string,
): QueryRequest {
  return {
    mode: "diagnosis",
    is_stream: true,
    diagnosis_id: session.diagnosis_id,
    answers,
    request_id: requestId,
    expected_revision: session.revision,
  };
}

export function buildResumeUnresolvedRequest(session: DiagnosisSession, requestId: string): QueryRequest {
  return {
    mode: "diagnosis",
    is_stream: true,
    diagnosis_id: session.diagnosis_id,
    request_id: requestId,
    expected_revision: session.revision,
    resume_unresolved: true,
  };
}

export function isDiagnosing(session: DiagnosisSession | null): boolean {
  return session?.status === "in_progress" && session.decision === null;
}
