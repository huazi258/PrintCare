import { AlertTriangle, CheckCircle2, CircleX, ClipboardCheck, FileWarning, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import type {
  DiagnosisAnswerDecision,
  DiagnosisDecision,
  DiagnosisInsufficientDecision,
  DiagnosisStatus,
  EvidenceExcerpt,
} from "@/types/api";


type DiagnosisResultProps = {
  decision: DiagnosisDecision;
  status: DiagnosisStatus;
  isFeedbackSubmitting?: boolean;
  onFeedback?: (status: "resolved" | "unresolved") => void;
  onResumeUnresolved?: () => void;
};

function DiagnosisEvidence({ evidence }: { evidence?: EvidenceExcerpt[] }) {
  if (!evidence?.length) {
    return <p className="text-sm leading-6 text-muted-foreground">当前结果没有可展示的证据摘录。</p>;
  }

  return (
    <div className="space-y-2">
      {evidence.map((item, index) => (
        <details key={`${item.source_id}-${index}`} className="rounded-lg border border-border bg-background px-3 py-2.5">
          <summary className="cursor-pointer text-sm font-medium text-foreground marker:text-primary">
            来源标识：{item.source_id}
          </summary>
          <div className="mt-3 space-y-2 border-t border-border pt-3 text-sm leading-6 text-muted-foreground">
            <p><span className="font-medium text-foreground">证据摘录：</span>{item.excerpt}</p>
            <p><span className="font-medium text-foreground">支持说明：</span>{item.support_text}</p>
          </div>
        </details>
      ))}
    </div>
  );
}

function AnswerResult({
  decision,
  status,
  isFeedbackSubmitting = false,
  onFeedback,
  onResumeUnresolved,
}: {
  decision: DiagnosisAnswerDecision;
  status: DiagnosisStatus;
  isFeedbackSubmitting?: boolean;
  onFeedback?: (status: "resolved" | "unresolved") => void;
  onResumeUnresolved?: () => void;
}) {
  const evidence = Array.from(new Map([
    ...decision.conclusion_evidence,
    ...decision.recommendations.flatMap((recommendation) => recommendation.evidence),
  ].map((item) => [`${item.source_id}:${item.excerpt}:${item.support_text}`, item])).values());
  const statusContent = status === "pending_verification"
    ? {
        icon: ClipboardCheck,
        title: "等待你的验证",
        description: "系统已提供基于本地资料的建议，但尚未确认问题是否已解决。",
        className: "border-primary/20 bg-primary/5 text-primary",
      }
    : status === "resolved"
      ? {
          icon: CheckCircle2,
          title: "已解决",
          description: "该状态仅表示用户反馈的问题已解决。",
          className: "border-emerald-600/20 bg-emerald-50 text-emerald-700",
        }
      : status === "unresolved"
        ? {
            icon: CircleX,
            title: "未解决",
            description: "该状态仅表示用户反馈尚未解决；是否继续诊断应由服务端会话状态决定。",
            className: "border-amber-600/20 bg-amber-50 text-amber-800",
          }
        : {
            icon: ClipboardCheck,
            title: "等待会话状态更新",
            description: "诊断结论不等于问题已解决。",
            className: "border-primary/20 bg-primary/5 text-primary",
          };
  const StatusIcon = statusContent.icon;

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-primary/20 bg-primary/5 p-5 sm:p-6">
        <p className="text-sm font-medium text-primary">诊断结论</p>
        <h2 className="mt-2 text-xl font-semibold leading-8 text-foreground">{decision.conclusion}</h2>
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-base font-semibold text-foreground">建议操作</h3>
        <ol className="mt-4 space-y-3">
          {decision.recommendations.map((recommendation, index) => (
            <li key={`${recommendation.text}-${index}`} className="flex gap-3 rounded-lg bg-muted/70 p-3 text-sm leading-6 text-foreground">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-card text-xs font-semibold text-primary">{index + 1}</span>
              <span>{recommendation.text}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-base font-semibold text-foreground">参考依据</h3>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">展开条目可查看服务端返回的来源标识与证据摘录。</p>
        <div className="mt-4"><DiagnosisEvidence evidence={evidence} /></div>
      </section>

      {decision.safety_notes.length ? (
        <section className="rounded-xl border border-amber-600/20 bg-amber-50 p-5">
          <h3 className="flex items-center gap-2 text-base font-semibold text-amber-900"><ShieldAlert className="size-5" aria-hidden="true" />安全提示</h3>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-900/90">
            {decision.safety_notes.map((note, index) => <li key={`${note}-${index}`}>• {note}</li>)}
          </ul>
        </section>
      ) : null}

      <section className={`rounded-xl border p-5 ${statusContent.className}`} aria-live="polite">
        <h3 className="flex items-center gap-2 text-base font-semibold"><StatusIcon className="size-5" aria-hidden="true" />{statusContent.title}</h3>
        <p className="mt-2 text-sm leading-6 text-foreground/80">{statusContent.description}</p>
        {status === "pending_verification" ? (
          <div className="mt-4 flex flex-wrap gap-3">
            <Button type="button" disabled={isFeedbackSubmitting || !onFeedback} onClick={() => onFeedback?.("resolved")}>
              {isFeedbackSubmitting ? "正在提交…" : "已解决"}
            </Button>
            <Button type="button" variant="outline" disabled={isFeedbackSubmitting || !onFeedback} onClick={() => onFeedback?.("unresolved")}>
              未解决
            </Button>
          </div>
        ) : null}
        {status === "unresolved" && onResumeUnresolved ? (
          <div className="mt-4">
            <Button type="button" variant="outline" disabled={isFeedbackSubmitting} onClick={onResumeUnresolved}>
              {isFeedbackSubmitting ? "正在请求继续诊断…" : "请求继续诊断"}
            </Button>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function InsufficientResult({ decision }: { decision: DiagnosisInsufficientDecision }) {
  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-amber-600/20 bg-amber-50 p-5 sm:p-6">
        <p className="flex items-center gap-2 text-sm font-medium text-amber-800"><FileWarning className="size-4" aria-hidden="true" />资料不足</p>
        <h2 className="mt-2 text-xl font-semibold leading-8 text-foreground">暂时无法做出可靠判断</h2>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">{decision.reason}</p>
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-base font-semibold text-foreground">已确认的信息</h3>
        {decision.confirmed_facts.length ? (
          <ul className="mt-3 space-y-2 text-sm leading-6 text-foreground">
            {decision.confirmed_facts.map((fact, index) => <li key={`${fact}-${index}`}>• {fact}</li>)}
          </ul>
        ) : <p className="mt-3 text-sm text-muted-foreground">尚无可确认的信息。</p>}
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <h3 className="text-base font-semibold text-foreground">后续建议</h3>
        <ol className="mt-3 space-y-2 text-sm leading-6 text-foreground">
          {decision.next_steps.map((step, index) => <li key={`${step}-${index}`}>{index + 1}. {step}</li>)}
        </ol>
      </section>
    </div>
  );
}

export function DiagnosisResult({ decision, status, isFeedbackSubmitting, onFeedback, onResumeUnresolved }: DiagnosisResultProps) {
  if (decision.action === "answer") {
    return <AnswerResult decision={decision} status={status} isFeedbackSubmitting={isFeedbackSubmitting} onFeedback={onFeedback} onResumeUnresolved={onResumeUnresolved} />;
  }

  if (decision.action === "insufficient") {
    return <InsufficientResult decision={decision} />;
  }

  return (
    <section className="rounded-xl border border-destructive/20 bg-destructive/5 p-5 text-sm text-destructive">
      <p className="flex items-center gap-2 font-medium"><AlertTriangle className="size-4" aria-hidden="true" />当前决策仍需要继续追问。</p>
    </section>
  );
}
