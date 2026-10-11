import { useMemo, useState } from "react";
import { ArrowLeft, ClipboardList, FlaskConical, History, MessageSquareText, Trash2 } from "lucide-react";

import { DeleteConfirmDialog } from "@/components/history/DeleteConfirmDialog";
import { HistoryFilters } from "@/components/history/HistoryFilters";
import { HistoryList } from "@/components/history/HistoryList";
import { deletePreviewRecord, filterHistoryRecords, type HistoryFilter, type HistoryRecord } from "@/components/history/history-state";
import { DiagnosisResult } from "@/components/diagnosis/DiagnosisResult";
import { EmptyState } from "@/components/EmptyState";
import { PageContainer } from "@/components/PageContainer";
import { ConversationMessage } from "@/components/qa/ConversationMessage";
import { Button } from "@/components/ui/button";

const previewRecords: HistoryRecord[] = [
  {
    id: "preview-qa",
    type: "qa",
    title: "K1 如何进行首次打印？",
    createdAt: "开发预览时间 · 今天 10:20",
    messages: [
      { id: "preview-qa-question", role: "user", content: "K1 如何进行首次打印？" },
      { id: "preview-qa-answer", role: "assistant", content: "开发预览回答：此处仅验证问答历史的阅读布局，真实回答与来源将由后续服务端读取接口提供。", sources: [] },
    ],
  },
  {
    id: "preview-diagnosis",
    type: "diagnosis",
    title: "第一层无法稳定附着",
    createdAt: "开发预览时间 · 昨天 16:40",
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

function HistoryDetail({ record, onBack, onDelete }: { record: HistoryRecord; onBack: () => void; onDelete: () => void }) {
  const session = record.type === "diagnosis" ? record.session : null;
  return (
    <section aria-labelledby="history-detail-title">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"><ArrowLeft className="size-4" aria-hidden="true" />返回历史记录</button>
      <header className="mt-5 flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0"><p className="text-sm font-medium text-primary">开发预览（模拟数据）</p><h1 id="history-detail-title" className="mt-1 break-words text-2xl font-semibold tracking-tight text-foreground">{record.title}</h1><p className="mt-2 text-sm text-muted-foreground">{record.createdAt}</p></div>
        <Button type="button" variant="outline" onClick={onDelete} className="self-start text-destructive hover:text-destructive"><Trash2 className="size-4" aria-hidden="true" />删除</Button>
      </header>
      {record.type === "qa" ? (
        <section aria-label="知识问答内容" className="mt-7">{record.messages.map((message) => <ConversationMessage key={message.id} message={message} />)}</section>
      ) : session ? (
        <section className="mt-7 space-y-6" aria-label="智能诊断详情">
          <div className="rounded-xl border border-border bg-card p-5"><p className="text-sm font-medium text-primary">原始故障描述</p><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-foreground">{session.original_problem}</p></div>
          <div className="rounded-xl border border-border bg-card p-5"><h2 className="text-base font-semibold text-foreground">已保存的问答轮次</h2>{session.rounds.length ? session.rounds.map((round, index) => <div key={index} className="mt-4 rounded-lg bg-muted/60 p-3 text-sm leading-6 text-foreground"><p className="font-medium">第 {index + 1} 轮</p><p className="mt-1 text-muted-foreground">问题数：{round.questions?.length ?? 0} · 已保存答案：{round.answers?.length ?? 0}</p></div>) : <p className="mt-3 text-sm text-muted-foreground">暂无已保存的问答轮次。</p>}</div>
          {session.decision ? <DiagnosisResult decision={session.decision} status={session.status} /> : <EmptyState icon={ClipboardList} title="尚未形成诊断结论" description="真实会话的当前状态应以后端读取结果为准。" />}
        </section>
      ) : null}
    </section>
  );
}

export function HistoryPage() {
  const isPreview = import.meta.env.DEV;
  const [showPreview, setShowPreview] = useState(false);
  const [records, setRecords] = useState<HistoryRecord[]>(previewRecords);
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const [query, setQuery] = useState("");
  const [selectedRecord, setSelectedRecord] = useState<HistoryRecord | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<HistoryRecord | null>(null);
  const visibleRecords = useMemo(() => filterHistoryRecords(showPreview ? records : [], filter, query), [filter, query, records, showPreview]);

  function confirmDelete() {
    if (!deleteTarget) return;
    setRecords((current) => deletePreviewRecord(current, deleteTarget.id));
    setSelectedRecord(null);
    setDeleteTarget(null);
  }

  if (selectedRecord) {
    return <PageContainer className="max-w-[900px] pb-8"><HistoryDetail record={selectedRecord} onBack={() => setSelectedRecord(null)} onDelete={() => setDeleteTarget(selectedRecord)} />{deleteTarget ? <DeleteConfirmDialog recordTitle={deleteTarget.title} onCancel={() => setDeleteTarget(null)} onConfirm={confirmDelete} /> : null}</PageContainer>;
  }

  return (
    <PageContainer className="max-w-[980px] pb-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div><p className="flex items-center gap-1.5 text-sm font-medium text-primary"><History className="size-4" aria-hidden="true" />当前浏览器</p><h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">历史记录</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">查看当前浏览器关联的知识问答与诊断记录。匿名访客历史不承诺跨设备同步。</p></div>
        {isPreview ? <Button type="button" variant="outline" onClick={() => setShowPreview((current) => !current)} className="self-start"><FlaskConical className="size-4" aria-hidden="true" />{showPreview ? "返回空状态" : "查看开发预览"}</Button> : null}
      </header>
      {showPreview ? <p className="mt-6 rounded-lg border border-dashed border-primary/35 bg-primary/5 px-4 py-3 text-sm leading-6 text-primary">开发预览（模拟数据）：搜索、筛选、详情与删除仅在本地状态中生效，不读取或删除真实历史。</p> : null}
      <div className="mt-7"><HistoryFilters filter={filter} query={query} onFilterChange={setFilter} onQueryChange={setQuery} /></div>
      <section className="mt-5" aria-label="历史记录列表">{showPreview && visibleRecords.length ? <HistoryList records={visibleRecords} onSelect={setSelectedRecord} /> : <EmptyState icon={showPreview ? MessageSquareText : History} title={showPreview ? "没有匹配的模拟记录" : "暂无可展示的历史记录"} description={showPreview ? "请调整搜索词或筛选条件。" : "真实历史读取将在后续联调；当前不会用本地缓存或模拟数据冒充服务端历史。"} />}</section>
      <p className="mt-5 text-xs leading-5 text-muted-foreground">知识问答当前仅支持按已知 session_id 读取或删除；后端尚未提供跨会话 QA 列表。诊断详情、列表与删除接口将在 T3-03 接入。</p>
    </PageContainer>
  );
}
