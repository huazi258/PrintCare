import { useEffect, useRef, useState } from "react";
import { AlertCircle, LoaderCircle, RotateCcw } from "lucide-react";

import { DiagnosisPreviewControls, type DiagnosisPreviewState } from "@/components/diagnosis/DiagnosisPreviewControls";
import { DiagnosisProgress } from "@/components/diagnosis/DiagnosisProgress";
import { DiagnosisQuestionGroup } from "@/components/diagnosis/DiagnosisQuestionGroup";
import { DiagnosisResult } from "@/components/diagnosis/DiagnosisResult";
import {
  buildDiagnosisAnswerRequest,
  buildDiagnosisStartRequest,
  buildResumeUnresolvedRequest,
  createDiagnosisRequestId,
  DIAGNOSIS_STORAGE_KEY,
  isDiagnosing,
} from "@/components/diagnosis/diagnosis-session";
import { DiagnosisStart } from "@/components/diagnosis/DiagnosisStart";
import { type DiagnosisSelections } from "@/components/diagnosis/diagnosis-state";
import { ApiError } from "@/services/http";
import { printCareApi } from "@/services/printcare-api";
import { subscribeToTask, type TaskStreamSubscription } from "@/services/sse";
import type {
  DiagnosisAnswerInput,
  DiagnosisAskDecision,
  DiagnosisDecision,
  DiagnosisInsufficientDecision,
  DiagnosisQuestion,
  DiagnosisSession,
  DiagnosisStatus,
  EvidenceExcerpt,
  ProgressEvent,
  QueryRequest,
} from "@/types/api";

type DiagnosisView = "start" | "questions" | "processing" | "result";

const mockEvidence: EvidenceExcerpt = { source_id: "preview:local-evidence", excerpt: "开发预览的证据摘录，不对应实际设备资料。", support_text: "仅用于检查证据组件的展开和排版。" };
const firstRoundQuestions: DiagnosisQuestion[] = [{ question_id: "build-plate-condition", text: "开始打印前，构建板表面是否已清洁且没有明显残留？", options: [{ option_id: "clean", text: "已清洁，没有明显残留", option_type: "normal" }, { option_id: "residue", text: "有可见残留或油污", option_type: "normal" }, { option_id: "unsure", text: "不确定", option_type: "uncertain" }], references: [mockEvidence] }];
const secondRoundQuestions: DiagnosisQuestion[] = [
  { question_id: "first-layer-pattern", text: "第一层材料落在构建板上时，主要呈现哪种情况？", options: [{ option_id: "not-stick", text: "线条无法附着或被喷嘴带起", option_type: "normal" }, { option_id: "partial-stick", text: "部分区域可以附着，其他区域翘起", option_type: "normal" }, { option_id: "unknown", text: "不确定", option_type: "uncertain" }], references: [mockEvidence] },
  { question_id: "recent-change", text: "近期是否有未列出的材料、环境或维护变化？", options: [{ option_id: "no-change", text: "没有其他变化", option_type: "normal" }, { option_id: "other-change", text: "其他情况", option_type: "other" }], references: [mockEvidence] },
];
const thirdRoundQuestions: DiagnosisQuestion[] = [
  { question_id: "material-condition", text: "当前使用的材料状态是否正常？", options: [{ option_id: "normal-material", text: "材料状态正常", option_type: "normal" }, { option_id: "possible-moisture", text: "材料可能受潮或状态未知", option_type: "uncertain" }], references: [mockEvidence] },
  { question_id: "start-process", text: "问题是在每次打印开始时都出现，还是偶发出现？", options: [{ option_id: "every-time", text: "每次开始打印时都出现", option_type: "normal" }, { option_id: "intermittent", text: "偶发出现", option_type: "normal" }, { option_id: "not-observed", text: "无法确认", option_type: "uncertain" }], references: [mockEvidence] },
  { question_id: "additional-observation", text: "是否还有其他需要补充的观察？", options: [{ option_id: "none", text: "没有其他观察", option_type: "normal" }, { option_id: "other-observation", text: "其他情况", option_type: "other" }], references: [mockEvidence] },
];
const answerDecision: DiagnosisDecision = { action: "answer", conclusion: "开发预览结论：此处仅展示已验证结论的界面结构。", conclusion_evidence: [mockEvidence], recommendations: [{ text: "开发预览建议：用于检查建议卡片的排版，不是实际维修指令。", evidence: [mockEvidence] }, { text: "真实建议必须由服务端依据本轮命中的可信资料生成并校验。", evidence: [mockEvidence] }], references: [{ source_id: mockEvidence.source_id }], safety_notes: ["开发预览：真实环境应遵循服务端返回的安全提示。"] };
const insufficientDecision: DiagnosisInsufficientDecision = { action: "insufficient", reason: "开发预览：本地资料不足以支持可靠判断。", confirmed_facts: ["开发预览中已确认用户描述已保留。"], next_steps: ["后续联调后，应仅呈现服务端返回的安全后续步骤。"] };

function previewQuestionState(previewState: DiagnosisPreviewState): { round: number; decision: DiagnosisAskDecision } {
  if (previewState === "ask-two") return { round: 2, decision: { action: "ask", questions: secondRoundQuestions } };
  if (previewState === "ask-three") return { round: 3, decision: { action: "ask", questions: thirdRoundQuestions } };
  return { round: 1, decision: { action: "ask", questions: firstRoundQuestions } };
}

function describeProgress(progress: ProgressEvent): string {
  if (progress.message?.trim()) return progress.message;
  if (progress.stage?.trim()) return `正在${progress.stage}`;
  return "正在根据本地设备资料处理诊断…";
}

function viewForSession(session: DiagnosisSession | null, isProcessing: boolean): DiagnosisView {
  if (!session) return "start";
  if (isProcessing || isDiagnosing(session)) return "processing";
  if (session.decision?.action === "ask") return "questions";
  return "result";
}

export function DiagnosisPage() {
  const previewParameter = new URLSearchParams(window.location.search).get("preview");
  const isPreview = import.meta.env.DEV && ["start", "ask-one", "ask-two", "ask-three", "processing", "answer-pending", "answer-resolved", "answer-unresolved", "insufficient", "error"].includes(previewParameter ?? "");
  const [problem, setProblem] = useState("");
  const [session, setSession] = useState<DiagnosisSession | null>(null);
  const [selections, setSelections] = useState<DiagnosisSelections>({});
  const [errorMessage, setErrorMessage] = useState<string | undefined>();
  const [statusNotice, setStatusNotice] = useState<string | undefined>();
  const [progressMessage, setProgressMessage] = useState<string | undefined>();
  const [isRestoring, setIsRestoring] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isFeedbackSubmitting, setIsFeedbackSubmitting] = useState(false);
  const [previewState, setPreviewState] = useState<DiagnosisPreviewState>((isPreview ? previewParameter : "start") as DiagnosisPreviewState);
  const [previewRound, setPreviewRound] = useState(1);
  const [previewDecision, setPreviewDecision] = useState<DiagnosisDecision | null>(null);
  const [previewStatus, setPreviewStatus] = useState<DiagnosisStatus>("in_progress");
  const streamRef = useRef<TaskStreamSubscription | null>(null);
  const requestAbortRef = useRef<AbortController | null>(null);
  const activeTaskIdRef = useRef<string | null>(null);
  const mountedRef = useRef(true);
  const requestIdsRef = useRef(new Map<string, string>());

  const persistSession = (nextSession: DiagnosisSession) => {
    if (!mountedRef.current) return;
    setSession(nextSession);
    setProblem(nextSession.original_problem);
    window.localStorage.setItem(DIAGNOSIS_STORAGE_KEY, nextSession.diagnosis_id);
  };

  const getRequestId = (operationKey: string) => {
    const existing = requestIdsRef.current.get(operationKey);
    if (existing) return existing;
    const requestId = createDiagnosisRequestId();
    requestIdsRef.current.set(operationKey, requestId);
    return requestId;
  };

  const finishTask = (taskId?: string) => {
    if (taskId && activeTaskIdRef.current !== taskId) return false;
    activeTaskIdRef.current = null;
    streamRef.current?.close();
    streamRef.current = null;
    if (mountedRef.current) {
      setIsProcessing(false);
      setProgressMessage(undefined);
    }
    return true;
  };

  const recoverPersistedSession = async (diagnosisId: string, notice?: string) => {
    const recovered = await printCareApi.getDiagnosis(diagnosisId);
    persistSession(recovered);
    if (notice && mountedRef.current) setStatusNotice(notice);
    return recovered;
  };

  const recoverAfterStreamIssue = async (diagnosisId: string, taskId: string, message: string) => {
    try {
      await recoverPersistedSession(diagnosisId, message);
      finishTask(taskId);
    } catch {
      if (!finishTask(taskId)) return;
      setErrorMessage("SSE 连接中断，且暂时无法读取已持久化的诊断会话。请稍后刷新页面恢复结果。");
    }
  };

  const subscribe = (taskId: string, diagnosisId: string) => {
    activeTaskIdRef.current = taskId;
    streamRef.current = subscribeToTask(taskId, {
      onProgress: (progress) => { if (activeTaskIdRef.current === taskId) setProgressMessage(describeProgress(progress)); },
      onDiagnosis: (nextSession) => { if (activeTaskIdRef.current === taskId) persistSession(nextSession); },
      onFinal: () => { if (activeTaskIdRef.current === taskId) void recoverAfterStreamIssue(diagnosisId, taskId, "已从服务端持久化会话恢复诊断结果。"); },
      onTaskError: ({ message }) => { streamRef.current?.close(); if (activeTaskIdRef.current === taskId) void recoverAfterStreamIssue(diagnosisId, taskId, message || "诊断任务未完成；已尝试读取已持久化会话。"); },
      onNetworkError: () => { void recoverAfterStreamIssue(diagnosisId, taskId, "SSE 连接中断，已从服务端持久化会话恢复当前状态。"); },
      onParseError: () => { if (activeTaskIdRef.current === taskId) setErrorMessage("服务端返回了无法解析的流式数据，正在等待已持久化结果。"); },
    });
  };

  useEffect(() => {
    if (isPreview) return;
    const diagnosisId = window.localStorage.getItem(DIAGNOSIS_STORAGE_KEY);
    if (!diagnosisId) return;
    const controller = new AbortController();
    setIsRestoring(true);
    printCareApi.getDiagnosis(diagnosisId, { signal: controller.signal })
      .then((recovered) => persistSession(recovered))
      .catch((error: unknown) => {
        if (controller.signal.aborted || !mountedRef.current) return;
        if (error instanceof ApiError && error.status === 404) { window.localStorage.removeItem(DIAGNOSIS_STORAGE_KEY); return; }
        setErrorMessage("当前诊断会话暂时无法读取；请检查服务后刷新页面。");
      })
      .finally(() => { if (mountedRef.current) setIsRestoring(false); });
    return () => controller.abort();
  }, [isPreview]);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; requestAbortRef.current?.abort(); streamRef.current?.close(); };
  }, []);

  const submitDiagnosis = async (payload: QueryRequest) => {
    if (isProcessing) return;
    const controller = new AbortController();
    requestAbortRef.current = controller;
    setErrorMessage(undefined);
    setStatusNotice(undefined);
    setProgressMessage("正在提交诊断信息…");
    setIsProcessing(true);
    try {
      const response = await printCareApi.submitQuery(payload, { signal: controller.signal });
      if (!("diagnosis_id" in response) || !response.task_id || !response.diagnosis_id) throw new Error("诊断服务未返回任务或会话标识。");
      window.localStorage.setItem(DIAGNOSIS_STORAGE_KEY, response.diagnosis_id);
      await recoverPersistedSession(response.diagnosis_id);
      subscribe(response.task_id, response.diagnosis_id);
    } catch (error) {
      if (controller.signal.aborted) return;
      setIsProcessing(false);
      setProgressMessage(undefined);
      if (error instanceof ApiError && error.status === 409 && session?.diagnosis_id) {
        try { await recoverPersistedSession(session.diagnosis_id, "会话版本已更新，已读取服务端最新状态。请根据最新状态继续操作。"); } catch { setErrorMessage(error.message); }
        return;
      }
      setErrorMessage(error instanceof Error ? error.message : "诊断请求失败，请稍后重试。");
    }
  };

  const resetToStart = () => {
    requestAbortRef.current?.abort();
    finishTask();
    setSession(null); setProblem(""); setSelections({}); setErrorMessage(undefined); setStatusNotice(undefined);
    window.localStorage.removeItem(DIAGNOSIS_STORAGE_KEY);
  };

  const handleStart = () => {
    const originalProblem = problem.trim();
    if (!originalProblem || isPreview) return;
    const requestId = getRequestId(`start:${originalProblem}`);
    void submitDiagnosis(buildDiagnosisStartRequest(originalProblem, requestId));
  };

  const handleAnswerSubmit = (answers: DiagnosisAnswerInput[]) => {
    if (!session || session.decision?.action !== "ask" || isPreview) return;
    const requestId = getRequestId(`answer:${session.diagnosis_id}:${session.revision}`);
    void submitDiagnosis(buildDiagnosisAnswerRequest(session, answers, requestId));
  };

  const handleFeedback = async (status: "resolved" | "unresolved") => {
    if (!session || session.status !== "pending_verification" || isFeedbackSubmitting || isPreview) return;
    setIsFeedbackSubmitting(true); setErrorMessage(undefined);
    try {
      persistSession(await printCareApi.submitDiagnosisFeedback(session.diagnosis_id, { status, expected_revision: session.revision }));
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        try { await recoverPersistedSession(session.diagnosis_id, "会话版本已更新，已读取服务端最新状态。"); } catch { setErrorMessage(error.message); }
      } else setErrorMessage(error instanceof Error ? error.message : "提交诊断反馈失败，请稍后重试。");
    } finally { if (mountedRef.current) setIsFeedbackSubmitting(false); }
  };

  const handleResumeUnresolved = () => {
    if (!session || session.status !== "unresolved" || isPreview) return;
    const requestId = getRequestId(`resume:${session.diagnosis_id}:${session.revision}`);
    void submitDiagnosis(buildResumeUnresolvedRequest(session, requestId));
  };

  const handlePreviewState = (nextState: DiagnosisPreviewState) => {
    setPreviewState(nextState); setErrorMessage(undefined); setStatusNotice(undefined); setProblem("开发预览：构建板上第一层材料无法稳定附着。"); setSelections({});
    if (nextState === "start") { setPreviewDecision(null); setPreviewRound(1); return; }
    if (nextState === "processing") { setPreviewDecision(null); setPreviewRound(1); return; }
    if (nextState === "error") { setPreviewDecision(null); setErrorMessage("开发预览：模拟的服务错误。未创建或更新任何真实诊断会话。"); return; }
    if (nextState === "insufficient") { setPreviewRound(3); setPreviewStatus("insufficient"); setPreviewDecision(insufficientDecision); return; }
    if (nextState.startsWith("answer-")) { setPreviewRound(2); setPreviewStatus(nextState === "answer-resolved" ? "resolved" : nextState === "answer-unresolved" ? "unresolved" : "pending_verification"); setPreviewDecision(answerDecision); return; }
    const preview = previewQuestionState(nextState); setPreviewRound(preview.round); setPreviewStatus("in_progress"); setPreviewDecision(preview.decision);
  };

  const previewView: DiagnosisView = previewState === "start" || previewState === "error" ? "start" : previewState === "processing" ? "processing" : previewDecision?.action === "ask" ? "questions" : "result";
  const view = isPreview ? previewView : viewForSession(session, isProcessing);
  const decision = isPreview ? previewDecision : session?.decision ?? null;
  const status = isPreview ? previewStatus : session?.status;
  const round = isPreview ? previewRound : session?.clarification_round ?? 1;
  const askDecision = decision?.action === "ask" ? decision : null;
  const resultDecision = decision?.action === "answer" || decision?.action === "insufficient" ? decision : null;
  const actualProcessing = isPreview ? previewState === "processing" : isProcessing || isDiagnosing(session);

  return <div className="mx-auto w-full max-w-[900px] pb-8">
    {isPreview ? <DiagnosisPreviewControls value={previewState} onChange={handlePreviewState} /> : null}
    {isRestoring ? <p className="mb-4 text-sm text-muted-foreground">正在恢复当前浏览器关联的诊断会话…</p> : null}
    {view === "start" ? <DiagnosisStart problem={problem} errorMessage={errorMessage} isProcessing={actualProcessing} onProblemChange={(value) => { setProblem(value); if (errorMessage) setErrorMessage(undefined); }} onStart={handleStart} /> : null}
    {view === "questions" || view === "processing" ? <section aria-labelledby="diagnosis-session-title">
      <header className="mb-6 rounded-xl border border-border bg-card p-5 shadow-[0_2px_10px_rgba(27,36,48,0.04)]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-sm font-medium text-primary">Creality K1</p><h1 id="diagnosis-session-title" className="mt-1 text-2xl font-semibold text-foreground">智能故障诊断</h1></div><button type="button" onClick={resetToStart} disabled={actualProcessing && !isPreview} className="inline-flex items-center gap-1.5 self-start rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"><RotateCcw className="size-4" aria-hidden="true" />重新描述问题</button></div>
        <p className="mt-4 rounded-lg bg-muted px-3 py-2.5 text-sm leading-6 text-muted-foreground"><span className="font-medium text-foreground">原始描述：</span>{problem || "尚未提供描述"}</p>
        <div className="mt-5"><DiagnosisProgress round={round} stage="questions" /></div>
      </header>
      {view === "processing" ? <section className="rounded-xl border border-border bg-card p-8 text-center shadow-[0_2px_10px_rgba(27,36,48,0.04)]" aria-live="polite"><LoaderCircle className="mx-auto size-7 animate-spin text-primary" aria-hidden="true" /><h2 className="mt-4 text-lg font-semibold text-foreground">正在处理诊断信息</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{isPreview ? "开发预览仅展示处理中状态，未请求真实诊断服务。" : progressMessage ?? "正在根据本地设备资料生成下一步结果…"}</p></section> : askDecision ? <DiagnosisQuestionGroup questions={askDecision.questions} selections={selections} isProcessing={actualProcessing} onSelectionChange={(questionId, optionId) => setSelections((current) => ({ ...current, [questionId]: { optionId, supplementalNote: current[questionId]?.supplementalNote } }))} onSupplementalNoteChange={(questionId, supplementalNote) => setSelections((current) => ({ ...current, [questionId]: { optionId: current[questionId]?.optionId ?? "", supplementalNote } }))} onSubmit={handleAnswerSubmit} /> : null}
    </section> : null}
    {view === "result" && resultDecision && status ? <section aria-labelledby="diagnosis-result-title"><header className="mb-6 rounded-xl border border-border bg-card p-5 shadow-[0_2px_10px_rgba(27,36,48,0.04)]"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-sm font-medium text-primary">Creality K1</p><h1 id="diagnosis-result-title" className="mt-1 text-2xl font-semibold text-foreground">智能故障诊断</h1></div><button type="button" onClick={resetToStart} className="inline-flex items-center gap-1.5 self-start rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"><RotateCcw className="size-4" aria-hidden="true" />重新描述问题</button></div><div className="mt-5"><DiagnosisProgress round={round} stage="result" /></div></header><DiagnosisResult decision={resultDecision} status={status} isFeedbackSubmitting={isFeedbackSubmitting} onFeedback={isPreview ? undefined : handleFeedback} onResumeUnresolved={isPreview ? undefined : handleResumeUnresolved} /></section> : null}
    {errorMessage && view !== "start" ? <p role="alert" className="mt-4 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{errorMessage}</p> : null}
    {statusNotice ? <p aria-live="polite" className="mt-4 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-primary">{statusNotice}</p> : null}
    {isPreview ? <p className="mt-6 flex gap-2 text-xs leading-5 text-muted-foreground"><AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />开发预览数据只用于视觉与交互检查；正常页面只展示服务端已持久化的真实会话结果。</p> : null}
  </div>;
}
