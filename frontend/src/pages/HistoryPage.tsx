import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ClipboardList, FlaskConical, History, LoaderCircle, MessageSquareText, Trash2 } from "lucide-react";

import { DiagnosisResult } from "@/components/diagnosis/DiagnosisResult";
import { EmptyState } from "@/components/EmptyState";
import { DeleteConfirmDialog } from "@/components/history/DeleteConfirmDialog";
import { HistoryFilters } from "@/components/history/HistoryFilters";
import { HistoryList } from "@/components/history/HistoryList";
import {
  deletePreviewRecord,
  filterHistoryRecords,
  removeHistoryRecord,
  sortHistoryRecords,
  type HistoryFilter,
  type HistoryRecord,
} from "@/components/history/history-state";
import { PageContainer } from "@/components/PageContainer";
import { ConversationMessage } from "@/components/qa/ConversationMessage";
import {
  historyToQaMessages,
  parseQaSessionIndex,
  QA_SESSION_INDEX_STORAGE_KEY,
  QA_SESSION_STORAGE_KEY,
  removeQaSessionIndex,
  upsertQaSessionIndex,
} from "@/components/qa/qa-session";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/services/http";
import { printCareApi } from "@/services/printcare-api";
import type { DiagnosisRound, DiagnosisSession, QueryHistoryItem } from "@/types/api";

const previewRecords: HistoryRecord[] = [
  {
    id: "preview-qa",
    type: "qa",
    title: "K1 如何进行首次打印？",
    createdAt: "开发预览时间 · 今天 10:20",
    sessionId: "preview-qa",
    isPreview: true,
    messages: [
      { id: "preview-qa-question", role: "user", content: "K1 如何进行首次打印？" },
      { id: "preview-qa-answer", role: "assistant", content: "开发预览回答：此处仅验证问答历史的阅读布局，真实回答将通过会话历史接口读取。", sources: [] },
    ],
  },
  {
    id: "preview-diagnosis",
    type: "diagnosis",
    title: "第一层无法稳定附着",
    createdAt: "开发预览时间 · 昨天 16:40",
    isPreview: true,
    session: {
      diagnosis_id: "preview-diagnosis",
      device_id: "creality-k1",
      device_model: "Creality K1",
      original_problem: "开发预览：第一层材料无法稳定附着。",
      status: "pending_verification",
      clarification_round: 1,
      revision: 1,
      facts: [],
      rounds: [{ questions: [{ question_id: "preview-question", text: "构建板表面是否已清洁？", options: [], references: [] }], answers: [{ question_id: "preview-question", option_id: "preview-option" }] }],
      decision: {
        action: "answer",
        conclusion: "开发预览结论：仅用于验证诊断历史详情结构。",
        conclusion_evidence: [],
        recommendations: [{ text: "开发预览建议不代表真实维修指导。", evidence: [] }],
        references: [],
        safety_notes: ["真实安全提示仅来自已验证的服务端结果。"],
      },
      feedback: null,
      created_at: null,
      updated_at: null,
    },
  },
];

function formatTime(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "时间未提供";
  const timestamp = timestampOf(value, Number.NaN);
  return Number.isNaN(timestamp)
    ? "时间未提供"
    : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(timestamp);
}

function timestampOf(value: string | number | null | undefined, fallback: number): number {
  if (typeof value === "number") return value < 100_000_000_000 ? value * 1000 : value;
  if (typeof value === "string" && /^\d+(?:\.\d+)?$/.test(value)) {
    const numeric = Number(value);
    return numeric < 100_000_000_000 ? numeric * 1000 : numeric;
  }
  const timestamp = value ? Date.parse(value) : Number.NaN;
  return Number.isNaN(timestamp) ? fallback : timestamp;
}

function toQaRecord(sessionId: string, items: QueryHistoryItem[], fallbackTime: number): HistoryRecord | null {
  const messages = historyToQaMessages(items);
  const question = messages.find((message) => message.role === "user");
  if (!question) return null;
  const latestTime = items.at(-1)?.ts ?? fallbackTime;
  return {
    id: `qa:${sessionId}`,
    type: "qa",
    title: question.content,
    createdAt: formatTime(latestTime),
    sortTimestamp: timestampOf(latestTime, fallbackTime),
    messages,
    sessionId,
  };
}

function toDiagnosisRecord(session: DiagnosisSession): HistoryRecord {
  const updatedAt = session.updated_at ?? session.created_at;
  return {
    id: `diagnosis:${session.diagnosis_id}`,
    type: "diagnosis",
    title: session.original_problem,
    createdAt: formatTime(updatedAt),
    session,
  };
}

function QuestionRound({ round, index }: { round: DiagnosisRound; index: number }) {
  const questions = round.questions ?? [];
  const answers = round.answers ?? [];
  return (
    <div className="mt-4 rounded-lg bg-muted/60 p-3 text-sm leading-6 text-foreground">
      <p className="font-medium">第 {index + 1} 轮</p>
      {questions.length ? (
        <ul className="mt-2 space-y-2">
          {questions.map((question) => {
            const answer = answers.find((candidate) => candidate.question_id === question.question_id);
            const option = question.options.find((candidate) => candidate.option_id === answer?.option_id);
            return <li key={question.question_id}><p>{question.text}</p><p className="text-muted-foreground">回答：{option?.text ?? answer?.option_id ?? "未保存"}{answer?.supplemental_note ? `；补充：${answer.supplemental_note}` : ""}</p></li>;
          })}
        </ul>
      ) : <p className="mt-1 text-muted-foreground">此轮未保存可展示的问题。</p>}
    </div>
  );
}

function HistoryDetail({
  record,
  isLoading,
  loadError,
  onBack,
  onDelete,
}: {
  record: HistoryRecord;
  isLoading: boolean;
  loadError?: string;
  onBack: () => void;
  onDelete: () => void;
}) {
  const session = record.type === "diagnosis" ? record.session : null;
  return (
    <section aria-labelledby="history-detail-title">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"><ArrowLeft className="size-4" aria-hidden="true" />返回历史记录</button>
      <header className="mt-5 flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0"><p className="text-sm font-medium text-primary">{record.isPreview ? "开发预览（模拟数据）" : record.type === "qa" ? "当前浏览器已登记的 QA 会话" : "当前浏览器关联的诊断会话"}</p><h1 id="history-detail-title" className="mt-1 break-words text-2xl font-semibold tracking-tight text-foreground">{record.title}</h1><p className="mt-2 text-sm text-muted-foreground">{record.createdAt}</p></div>
        <Button type="button" variant="outline" onClick={onDelete} className="self-start text-destructive hover:text-destructive"><Trash2 className="size-4" aria-hidden="true" />删除</Button>
      </header>
      {isLoading ? <p className="mt-6 flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" />正在读取最新详情…</p> : null}
      {loadError ? <p role="alert" className="mt-6 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{loadError}</p> : null}
      {record.type === "qa" ? <section aria-label="知识问答内容" className="mt-7">{record.messages.map((message) => <ConversationMessage key={message.id} message={message} />)}</section> : session ? <section className="mt-7 space-y-6" aria-label="智能诊断详情"><div className="rounded-xl border border-border bg-card p-5"><p className="text-sm font-medium text-primary">原始故障描述</p><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-foreground">{session.original_problem}</p></div><div className="rounded-xl border border-border bg-card p-5"><h2 className="text-base font-semibold text-foreground">已保存的问答轮次</h2>{session.rounds.length ? session.rounds.map((round, index) => <QuestionRound key={index} round={round} index={index} />) : <p className="mt-3 text-sm text-muted-foreground">暂无已保存的问答轮次。</p>}</div>{session.decision ? <DiagnosisResult decision={session.decision} status={session.status} /> : <EmptyState icon={ClipboardList} title="尚未形成诊断结论" description="当前状态以后端读取结果为准。" />}</section> : null}
    </section>
  );
}

export function HistoryPage() {
  const isPreview = import.meta.env.DEV && new URLSearchParams(window.location.search).get("preview") === "history";
  const [records, setRecords] = useState<HistoryRecord[]>(isPreview ? previewRecords : []);
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedRecord, setSelectedRecord] = useState<HistoryRecord | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<HistoryRecord | null>(null);
  const [isLoading, setIsLoading] = useState(!isPreview);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [loadError, setLoadError] = useState<string | undefined>();
  const [detailError, setDetailError] = useState<string | undefined>();
  const [deleteError, setDeleteError] = useState<string | undefined>();
  const [notice, setNotice] = useState<string | undefined>();

  const loadRecords = useCallback(async (signal?: AbortSignal) => {
    if (isPreview) return;
    setIsLoading(true); setLoadError(undefined);
    const currentSessionId = window.localStorage.getItem(QA_SESSION_STORAGE_KEY);
    let qaSessions = parseQaSessionIndex(window.localStorage.getItem(QA_SESSION_INDEX_STORAGE_KEY));
    if (currentSessionId) {
      qaSessions = upsertQaSessionIndex(qaSessions, currentSessionId);
      window.localStorage.setItem(QA_SESSION_INDEX_STORAGE_KEY, JSON.stringify(qaSessions));
    }
    const [diagnosisResult, ...qaResults] = await Promise.allSettled([
      printCareApi.listDiagnoses({ signal }),
      ...qaSessions.map((entry) => printCareApi.getQueryHistory(entry.sessionId, { signal })),
    ]);
    if (signal?.aborted) return;
    const nextRecords: HistoryRecord[] = [];
    const warnings: string[] = [];
    if (diagnosisResult.status === "fulfilled") nextRecords.push(...diagnosisResult.value.items.map(toDiagnosisRecord));
    else warnings.push("诊断历史暂时无法读取。");
    qaResults.forEach((result, index) => {
      if (result.status !== "fulfilled") { warnings.push("部分已登记的问答会话暂时无法读取。"); return; }
      const record = toQaRecord(qaSessions[index].sessionId, result.value.items, qaSessions[index].updatedAt);
      if (record) nextRecords.push(record);
    });
    if (diagnosisResult.status === "rejected" && qaResults.every((result) => result.status === "rejected")) {
      setLoadError("历史记录暂时无法读取，请检查查询服务后重试。");
    }
    if (warnings.length) setNotice([...new Set(warnings)].join(" "));
    setRecords(sortHistoryRecords(nextRecords));
    setIsLoading(false);
  }, [isPreview]);

  useEffect(() => {
    const controller = new AbortController();
    void loadRecords(controller.signal);
    return () => controller.abort();
  }, [loadRecords]);

  const visibleRecords = useMemo(() => filterHistoryRecords(records, filter, query), [filter, query, records]);

  const selectRecord = async (record: HistoryRecord) => {
    setSelectedRecord(record); setDetailError(undefined);
    if (record.type !== "diagnosis" || record.isPreview) return;
    setIsDetailLoading(true);
    try {
      const session = await printCareApi.getDiagnosis(record.session.diagnosis_id);
      const updated = toDiagnosisRecord(session);
      setRecords((current) => current.map((item) => item.id === updated.id ? updated : item));
      setSelectedRecord(updated);
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : "诊断详情暂时无法读取。");
    } finally { setIsDetailLoading(false); }
  };

  const confirmDelete = async () => {
    if (!deleteTarget || isDeleting) return;
    if (deleteTarget.isPreview) {
      setRecords((current) => deletePreviewRecord(current, deleteTarget.id));
      setSelectedRecord(null); setDeleteTarget(null); return;
    }
    setIsDeleting(true); setDeleteError(undefined);
    try {
      if (deleteTarget.type === "qa") {
        await printCareApi.clearQueryHistory(deleteTarget.sessionId);
        const sessions = removeQaSessionIndex(parseQaSessionIndex(window.localStorage.getItem(QA_SESSION_INDEX_STORAGE_KEY)), deleteTarget.sessionId);
        window.localStorage.setItem(QA_SESSION_INDEX_STORAGE_KEY, JSON.stringify(sessions));
      } else await printCareApi.deleteDiagnosis(deleteTarget.session.diagnosis_id);
      setRecords((current) => removeHistoryRecord(current, deleteTarget.id));
      setSelectedRecord(null); setDeleteTarget(null); setNotice("记录已删除。");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) setDeleteError("该记录已不存在，刷新列表后将不再显示。");
      else setDeleteError(error instanceof Error ? error.message : "删除记录失败，请稍后重试。");
    } finally { setIsDeleting(false); }
  };

  if (selectedRecord) return <PageContainer className="max-w-[900px] pb-8"><HistoryDetail record={selectedRecord} isLoading={isDetailLoading} loadError={detailError} onBack={() => { setSelectedRecord(null); setDetailError(undefined); }} onDelete={() => setDeleteTarget(selectedRecord)} />{deleteTarget ? <DeleteConfirmDialog recordTitle={deleteTarget.title} errorMessage={deleteError} isDeleting={isDeleting} onCancel={() => { if (!isDeleting) { setDeleteTarget(null); setDeleteError(undefined); } }} onConfirm={confirmDelete} /> : null}</PageContainer>;

  return <PageContainer className="max-w-[980px] pb-8">
    <header><p className="flex items-center gap-1.5 text-sm font-medium text-primary"><History className="size-4" aria-hidden="true" />当前浏览器</p><h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">历史记录</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">查看当前浏览器关联的知识问答与诊断记录。知识问答仅显示此浏览器已登记的会话，匿名访客历史不承诺跨设备同步。</p></header>
    {isPreview ? <p className="mt-6 flex gap-2 rounded-lg border border-dashed border-primary/35 bg-primary/5 px-4 py-3 text-sm leading-6 text-primary"><FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden="true" />开发预览（模拟数据）：通过 <code>?preview=history</code> 进入，未读取或删除真实历史。</p> : null}
    <div className="mt-7"><HistoryFilters filter={filter} query={query} onFilterChange={setFilter} onQueryChange={setQuery} /></div>
    {loadError ? <p role="alert" className="mt-5 rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">{loadError}</p> : null}
    {notice ? <p aria-live="polite" className="mt-5 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary">{notice}</p> : null}
    <section className="mt-5" aria-label="历史记录列表">{isLoading ? <div className="flex min-h-44 items-center justify-center gap-2 rounded-xl border border-border bg-card text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" />正在读取历史记录…</div> : visibleRecords.length ? <HistoryList records={visibleRecords} onSelect={selectRecord} /> : <EmptyState icon={isPreview ? MessageSquareText : History} title={isPreview ? "没有匹配的模拟记录" : "暂无可展示的历史记录"} description={isPreview ? "请调整搜索词或筛选条件。" : "新建问答或诊断后，记录会显示在这里。问答仅能列出当前浏览器已登记的会话。"} />}</section>
    {!isPreview ? <p className="mt-5 text-xs leading-5 text-muted-foreground">诊断列表、详情和删除由服务端按匿名访客 Cookie 关联。QA 后端目前没有跨会话列表接口，因此本页仅使用浏览器本地会话索引定位可读取的 QA 历史。</p> : null}
  </PageContainer>;
}
