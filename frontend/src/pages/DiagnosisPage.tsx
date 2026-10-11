import { useState } from "react";
import { AlertCircle, LoaderCircle, RotateCcw } from "lucide-react";

import { DiagnosisPreviewControls, type DiagnosisPreviewState } from "@/components/diagnosis/DiagnosisPreviewControls";
import { DiagnosisProgress } from "@/components/diagnosis/DiagnosisProgress";
import { DiagnosisQuestionGroup } from "@/components/diagnosis/DiagnosisQuestionGroup";
import { DiagnosisResult } from "@/components/diagnosis/DiagnosisResult";
import { DiagnosisStart } from "@/components/diagnosis/DiagnosisStart";
import type {
  DiagnosisAnswerInput,
  DiagnosisAskDecision,
  DiagnosisDecision,
  DiagnosisInsufficientDecision,
  DiagnosisQuestion,
  DiagnosisStatus,
  EvidenceExcerpt,
} from "@/types/api";

import { type DiagnosisSelections } from "@/components/diagnosis/diagnosis-state";

type DiagnosisView = "start" | "questions" | "processing" | "result";

const mockEvidence: EvidenceExcerpt = {
  source_id: "preview:local-evidence",
  excerpt: "开发预览的证据摘录，不对应实际设备资料。",
  support_text: "仅用于检查证据组件的展开和排版。",
};

const firstRoundQuestions: DiagnosisQuestion[] = [
  {
    question_id: "build-plate-condition",
    text: "开始打印前，构建板表面是否已清洁且没有明显残留？",
    options: [
      { option_id: "clean", text: "已清洁，没有明显残留", option_type: "normal" },
      { option_id: "residue", text: "有可见残留或油污", option_type: "normal" },
      { option_id: "unsure", text: "不确定", option_type: "uncertain" },
    ],
    references: [mockEvidence],
  },
];

const secondRoundQuestions: DiagnosisQuestion[] = [
  {
    question_id: "first-layer-pattern",
    text: "第一层材料落在构建板上时，主要呈现哪种情况？",
    options: [
      { option_id: "not-stick", text: "线条无法附着或被喷嘴带起", option_type: "normal" },
      { option_id: "partial-stick", text: "部分区域可以附着，其他区域翘起", option_type: "normal" },
      { option_id: "unknown", text: "不确定", option_type: "uncertain" },
    ],
    references: [mockEvidence],
  },
  {
    question_id: "recent-change",
    text: "近期是否有未列出的材料、环境或维护变化？",
    options: [
      { option_id: "no-change", text: "没有其他变化", option_type: "normal" },
      { option_id: "other-change", text: "其他情况", option_type: "other" },
    ],
    references: [mockEvidence],
  },
];

const thirdRoundQuestions: DiagnosisQuestion[] = [
  {
    question_id: "material-condition",
    text: "当前使用的材料状态是否正常？",
    options: [
      { option_id: "normal-material", text: "材料状态正常", option_type: "normal" },
      { option_id: "possible-moisture", text: "材料可能受潮或状态未知", option_type: "uncertain" },
    ],
    references: [mockEvidence],
  },
  {
    question_id: "start-process",
    text: "问题是在每次打印开始时都出现，还是偶发出现？",
    options: [
      { option_id: "every-time", text: "每次开始打印时都出现", option_type: "normal" },
      { option_id: "intermittent", text: "偶发出现", option_type: "normal" },
      { option_id: "not-observed", text: "无法确认", option_type: "uncertain" },
    ],
    references: [mockEvidence],
  },
  {
    question_id: "additional-observation",
    text: "是否还有其他需要补充的观察？",
    options: [
      { option_id: "none", text: "没有其他观察", option_type: "normal" },
      { option_id: "other-observation", text: "其他情况", option_type: "other" },
    ],
    references: [mockEvidence],
  },
];

const answerDecision: DiagnosisDecision = {
  action: "answer",
  conclusion: "开发预览结论：此处仅展示已验证结论的界面结构。",
  conclusion_evidence: [mockEvidence],
  recommendations: [
    { text: "开发预览建议：用于检查建议卡片的排版，不是实际维修指令。", evidence: [mockEvidence] },
    { text: "真实建议必须由服务端依据本轮命中的可信资料生成并校验。", evidence: [mockEvidence] },
  ],
  references: [{ source_id: mockEvidence.source_id }],
  safety_notes: ["开发预览：真实环境应遵循服务端返回的安全提示。"],
};

const insufficientDecision: DiagnosisInsufficientDecision = {
  action: "insufficient",
  reason: "开发预览：本地资料不足以支持可靠判断。",
  confirmed_facts: ["开发预览中已确认用户描述已保留。"],
  next_steps: ["后续联调后，应仅呈现服务端返回的安全后续步骤。"],
};

function previewQuestionState(previewState: DiagnosisPreviewState): { round: number; decision: DiagnosisAskDecision } {
  if (previewState === "ask-two") {
    return { round: 2, decision: { action: "ask", questions: secondRoundQuestions } };
  }
  if (previewState === "ask-three") {
    return { round: 3, decision: { action: "ask", questions: thirdRoundQuestions } };
  }
  return { round: 1, decision: { action: "ask", questions: firstRoundQuestions } };
}

export function DiagnosisPage() {
  const isPreview = import.meta.env.DEV;
  const [problem, setProblem] = useState("");
  const [view, setView] = useState<DiagnosisView>("start");
  const [round, setRound] = useState(1);
  const [questionDecision, setQuestionDecision] = useState<DiagnosisAskDecision>({ action: "ask", questions: [] });
  const [selections, setSelections] = useState<DiagnosisSelections>({});
  const [result, setResult] = useState<{ decision: DiagnosisDecision; status: DiagnosisStatus } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | undefined>();
  const [previewState, setPreviewState] = useState<DiagnosisPreviewState>("start");

  function resetToStart() {
    setView("start");
    setRound(1);
    setQuestionDecision({ action: "ask", questions: [] });
    setSelections({});
    setResult(null);
    setErrorMessage(undefined);
    setPreviewState("start");
  }

  function handleStart() {
    setErrorMessage("诊断服务尚待联调。你的故障描述已保留，尚未发送或创建诊断会话。");
  }

  function handleAnswerSubmit(answers: DiagnosisAnswerInput[]) {
    void answers;
    if (isPreview) {
      setView("processing");
      setErrorMessage(undefined);
      setPreviewState("processing");
      return;
    }
    setErrorMessage("诊断服务尚待联调。本轮答案未发送，当前选择仍保留在页面中。");
  }

  function handlePreviewState(nextState: DiagnosisPreviewState) {
    setPreviewState(nextState);
    setErrorMessage(undefined);
    setProblem("开发预览：构建板上第一层材料无法稳定附着。");
    setSelections({});

    if (nextState === "start") {
      resetToStart();
      return;
    }
    if (nextState === "processing") {
      const preview = previewQuestionState("ask-one");
      setRound(preview.round);
      setQuestionDecision(preview.decision);
      setView("processing");
      return;
    }
    if (nextState === "error") {
      setView("start");
      setErrorMessage("开发预览：模拟的服务错误。未创建或更新任何真实诊断会话。");
      return;
    }
    if (nextState === "insufficient") {
      setRound(3);
      setResult({ decision: insufficientDecision, status: "insufficient" });
      setView("result");
      return;
    }
    if (nextState === "answer-pending" || nextState === "answer-resolved" || nextState === "answer-unresolved") {
      setRound(2);
      setResult({
        decision: answerDecision,
        status: nextState === "answer-resolved" ? "resolved" : nextState === "answer-unresolved" ? "unresolved" : "pending_verification",
      });
      setView("result");
      return;
    }

    const preview = previewQuestionState(nextState);
    setRound(preview.round);
    setQuestionDecision(preview.decision);
    setView("questions");
  }

  const isProcessing = view === "processing";

  return (
    <div className="mx-auto w-full max-w-[900px] pb-8">
      {isPreview ? <DiagnosisPreviewControls value={previewState} onChange={handlePreviewState} /> : null}

      {view === "start" ? (
        <DiagnosisStart
          problem={problem}
          errorMessage={errorMessage}
          onProblemChange={(value) => {
            setProblem(value);
            if (errorMessage) setErrorMessage(undefined);
          }}
          onStart={handleStart}
        />
      ) : null}

      {view === "questions" || view === "processing" ? (
        <section aria-labelledby="diagnosis-session-title">
          <header className="mb-6 rounded-xl border border-border bg-card p-5 shadow-[0_2px_10px_rgba(27,36,48,0.04)]">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-medium text-primary">Creality K1</p>
                <h1 id="diagnosis-session-title" className="mt-1 text-2xl font-semibold text-foreground">智能故障诊断</h1>
              </div>
              <button type="button" onClick={resetToStart} className="inline-flex items-center gap-1.5 self-start rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30">
                <RotateCcw className="size-4" aria-hidden="true" />重新描述问题
              </button>
            </div>
            <p className="mt-4 rounded-lg bg-muted px-3 py-2.5 text-sm leading-6 text-muted-foreground">
              <span className="font-medium text-foreground">原始描述：</span>{problem || "尚未提供描述"}
            </p>
            <div className="mt-5"><DiagnosisProgress round={round} stage="questions" /></div>
          </header>

          {isProcessing ? (
            <section className="rounded-xl border border-border bg-card p-8 text-center shadow-[0_2px_10px_rgba(27,36,48,0.04)]" aria-live="polite">
              <LoaderCircle className="mx-auto size-7 animate-spin text-primary" aria-hidden="true" />
              <h2 className="mt-4 text-lg font-semibold text-foreground">正在处理本轮信息</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">开发预览仅展示处理中状态，未请求真实诊断服务。</p>
            </section>
          ) : (
            <DiagnosisQuestionGroup
              questions={questionDecision.questions}
              selections={selections}
              isProcessing={false}
              onSelectionChange={(questionId, optionId) => setSelections((current) => ({
                ...current,
                [questionId]: { optionId, supplementalNote: current[questionId]?.supplementalNote },
              }))}
              onSupplementalNoteChange={(questionId, supplementalNote) => setSelections((current) => ({
                ...current,
                [questionId]: { optionId: current[questionId]?.optionId ?? "", supplementalNote },
              }))}
              onSubmit={handleAnswerSubmit}
            />
          )}
          {errorMessage ? <p role="alert" className="mt-4 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{errorMessage}</p> : null}
        </section>
      ) : null}

      {view === "result" && result ? (
        <section aria-labelledby="diagnosis-result-title">
          <header className="mb-6 rounded-xl border border-border bg-card p-5 shadow-[0_2px_10px_rgba(27,36,48,0.04)]">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-medium text-primary">Creality K1</p>
                <h1 id="diagnosis-result-title" className="mt-1 text-2xl font-semibold text-foreground">智能故障诊断</h1>
              </div>
              <button type="button" onClick={resetToStart} className="inline-flex items-center gap-1.5 self-start rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30">
                <RotateCcw className="size-4" aria-hidden="true" />重新描述问题
              </button>
            </div>
            <div className="mt-5"><DiagnosisProgress round={round} stage="result" /></div>
          </header>
          <DiagnosisResult decision={result.decision} status={result.status} />
        </section>
      ) : null}

      {isPreview ? (
        <p className="mt-6 flex gap-2 text-xs leading-5 text-muted-foreground"><AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />开发预览数据只用于视觉与交互检查；生产模式不会展示这些虚构内容。</p>
      ) : null}
    </div>
  );
}
