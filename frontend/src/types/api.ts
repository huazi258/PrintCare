export type QueryMode = "qa" | "diagnosis";

export interface QueryRequest {
  query?: string;
  session_id?: string;
  is_stream?: boolean;
  device_id?: string;
  mode?: QueryMode;
  original_problem?: string;
  diagnosis_id?: string;
  answers?: DiagnosisAnswerInput[];
  request_id?: string;
  expected_revision?: number;
  resume_unresolved?: boolean;
}

export interface QueryResponse {
  message: string;
  session_id: string;
  answer: string;
  task_id: string;
}

export interface StreamSubmitResponse {
  message: string;
  session_id?: string;
  task_id: string;
  diagnosis_id?: string;
  revision?: number;
}

export interface TaskStatus {
  status: string;
  running_list: string[];
  done_list: string[];
  durations: Record<string, number>;
  answer: string;
  error: string | null;
  image_urls: string[];
  diagnosis: DiagnosisSession | null;
}

export interface QueryHistoryItem {
  _id: string;
  session_id: string;
  role: string;
  text: string;
  rewritten_query: string;
  item_names: string[];
  ts: string | number | null;
}

export interface QueryHistoryResponse {
  session_id: string;
  items: QueryHistoryItem[];
}

export interface UploadResponse {
  message: string;
  task_id: string;
}

export interface ImportTaskStatus {
  status: string;
  running_list: string[];
  done_list: string[];
  durations: Record<string, number>;
}

export interface DiagnosisAnswerInput {
  question_id: string;
  option_id: string;
  supplemental_note?: string | null;
}

export interface EvidenceReference {
  source_id: string;
}

export interface EvidenceExcerpt extends EvidenceReference {
  excerpt: string;
  support_text: string;
}

export interface DiagnosisOption {
  option_id: string;
  text: string;
  option_type: "normal" | "uncertain" | "other";
}

export interface DiagnosisQuestion {
  question_id: string;
  text: string;
  options: DiagnosisOption[];
  references: EvidenceExcerpt[];
}

export interface DiagnosisAskDecision {
  action: "ask";
  questions: DiagnosisQuestion[];
}

export interface DiagnosisRecommendation {
  text: string;
  evidence: EvidenceExcerpt[];
}

export interface DiagnosisAnswerDecision {
  action: "answer";
  conclusion: string;
  conclusion_evidence: EvidenceExcerpt[];
  recommendations: DiagnosisRecommendation[];
  references: EvidenceReference[];
  safety_notes: string[];
}

export interface DiagnosisInsufficientDecision {
  action: "insufficient";
  reason: string;
  confirmed_facts: string[];
  next_steps: string[];
}

export type DiagnosisDecision =
  | DiagnosisAskDecision
  | DiagnosisAnswerDecision
  | DiagnosisInsufficientDecision;

export type DiagnosisStatus =
  | "in_progress"
  | "pending_verification"
  | "resolved"
  | "unresolved"
  | "insufficient"
  | "ended";

export interface DiagnosisFeedback {
  status: "resolved" | "unresolved";
  updated_at?: string;
}

export interface DiagnosisRound {
  questions?: DiagnosisQuestion[];
  answers?: DiagnosisAnswerInput[];
  [field: string]: unknown;
}

export interface DiagnosisSession {
  diagnosis_id: string;
  device_id: string;
  device_model: string | null;
  original_problem: string;
  status: DiagnosisStatus;
  clarification_round: number;
  revision: number;
  facts: unknown[];
  rounds: DiagnosisRound[];
  decision: DiagnosisDecision | null;
  feedback: DiagnosisFeedback | null;
  created_at: string | null;
  updated_at: string | null;
  task_id?: string;
  idempotent?: boolean;
  processing?: boolean;
  active_task_id?: string | null;
}

export interface DiagnosisListResponse {
  items: DiagnosisSession[];
}

export interface DiagnosisFeedbackRequest {
  status: "resolved" | "unresolved";
  expected_revision: number;
}

export interface DiagnosisEndRequest {
  expected_revision: number;
}

export interface ProgressEvent {
  status?: string;
  done_list?: string[];
  running_list?: string[];
  stage?: string;
  message?: string;
}

export interface DeltaEvent {
  delta: string;
}

export interface FinalEvent {
  answer?: string;
  status?: string;
  diagnosis_id?: string;
  idempotent?: boolean;
  processing?: boolean;
  active_task_id?: string | null;
}

export interface TaskErrorEvent {
  code: string;
  message: string;
}
