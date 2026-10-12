import { useEffect, useRef, useState } from "react";
import { FlaskConical, LockKeyhole, UploadCloud } from "lucide-react";

import { DocumentList } from "@/components/admin/DocumentList";
import { DocumentUploader } from "@/components/admin/DocumentUploader";
import {
  IMPORT_POLL_INTERVAL_MS,
  canStartImport,
  importPreviewTasks,
  isImportTaskFailure,
  isImportTaskTerminal,
  shouldContinueImportPolling,
  type ImportPreviewKind,
} from "@/components/admin/admin-state";
import { ImportTaskProgress } from "@/components/admin/ImportTaskProgress";
import { EmptyState } from "@/components/EmptyState";
import { PageContainer } from "@/components/PageContainer";
import { ApiError } from "@/services/http";
import { printCareApi } from "@/services/printcare-api";
import type { ImportTaskStatus } from "@/types/api";

export function AdminPage() {
  const isPreview = import.meta.env.DEV && new URLSearchParams(window.location.search).get("preview") === "admin";
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | undefined>();
  const [statusNotice, setStatusNotice] = useState<string | undefined>();
  const [taskError, setTaskError] = useState<string | undefined>();
  const [liveTask, setLiveTask] = useState<ImportTaskStatus | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [previewKind, setPreviewKind] = useState<ImportPreviewKind>("idle");
  const pollingTimerRef = useRef<ReturnType<typeof window.setTimeout> | null>(null);
  const uploadAbortRef = useRef<AbortController | null>(null);
  const statusAbortRef = useRef<AbortController | null>(null);
  const uploadInFlightRef = useRef(false);
  const activeTaskIdRef = useRef<string | null>(null);
  const mountedRef = useRef(true);
  const task = isPreview ? (previewKind === "idle" ? null : importPreviewTasks[previewKind]) : liveTask;
  const previewError = previewKind === "failed" ? "开发预览：此错误仅用于验证导入失败提示，未发生真实上传或导入。" : undefined;

  const stopPolling = () => {
    if (pollingTimerRef.current) window.clearTimeout(pollingTimerRef.current);
    pollingTimerRef.current = null;
    statusAbortRef.current?.abort();
    statusAbortRef.current = null;
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      stopPolling();
      uploadAbortRef.current?.abort();
    };
  }, []);

  const pollTask = async (taskId: string, completedAttempts: number) => {
    if (activeTaskIdRef.current !== taskId) return;
    const controller = new AbortController();
    statusAbortRef.current = controller;
    try {
      const nextTask = await printCareApi.getImportStatus(taskId, { signal: controller.signal });
      if (!mountedRef.current || activeTaskIdRef.current !== taskId) return;
      setLiveTask(nextTask);

      if (isImportTaskTerminal(nextTask.status)) {
        activeTaskIdRef.current = null;
        uploadInFlightRef.current = false;
        setIsBusy(false);
        if (isImportTaskFailure(nextTask.status)) {
          setTaskError("服务端报告导入失败。当前状态接口未返回具体失败原因，请查看导入服务日志。");
        } else {
          setStatusNotice("导入任务已完成。此状态来自服务端任务接口，不以上传 HTTP 响应代替完成结果。");
          setSelectedFile(null);
        }
        return;
      }

      const nextAttempt = completedAttempts + 1;
      if (!shouldContinueImportPolling(nextTask.status, nextAttempt)) {
        activeTaskIdRef.current = null;
        uploadInFlightRef.current = false;
        setIsBusy(false);
        setTaskError("任务仍未返回完成或失败状态，已停止自动查询。请稍后刷新页面重新确认服务端状态。");
        return;
      }
      pollingTimerRef.current = window.setTimeout(() => {
        void pollTask(taskId, nextAttempt);
      }, IMPORT_POLL_INTERVAL_MS);
    } catch (error) {
      if (controller.signal.aborted || !mountedRef.current || activeTaskIdRef.current !== taskId) return;
      activeTaskIdRef.current = null;
      uploadInFlightRef.current = false;
      setIsBusy(false);
      setTaskError(error instanceof Error ? `读取导入任务状态失败：${error.message}` : "读取导入任务状态失败，请稍后重试。");
    }
  };

  const handleUpload = async () => {
    const file = selectedFile;
    if (!file || !canStartImport(true, isBusy) || uploadInFlightRef.current) return;
    if (isPreview) {
      setUploadError("开发预览不会上传文件或创建导入任务。请在不带 ?preview=admin 的页面执行真实导入。");
      return;
    }

    stopPolling();
    setUploadError(undefined);
    setTaskError(undefined);
    setStatusNotice("正在上传文件并创建导入任务…");
    uploadInFlightRef.current = true;
    setIsBusy(true);
    const controller = new AbortController();
    uploadAbortRef.current = controller;
    try {
      const response = await printCareApi.uploadDocument(file, "creality-k1", { signal: controller.signal });
      if (!response.task_id) throw new Error("上传服务未返回任务标识。");
      if (!mountedRef.current) return;
      activeTaskIdRef.current = response.task_id;
      setLiveTask({ status: "pending", running_list: [], done_list: [], durations: {} });
      setStatusNotice("文件已提交，正在读取服务端导入任务状态…");
      await pollTask(response.task_id, 0);
    } catch (error) {
      if (controller.signal.aborted || !mountedRef.current) return;
      activeTaskIdRef.current = null;
      uploadInFlightRef.current = false;
      setIsBusy(false);
      setStatusNotice(undefined);
      if (error instanceof ApiError) setUploadError(error.message);
      else setUploadError(error instanceof Error ? error.message : "上传失败，请稍后重试。");
    }
  };

  return (
    <PageContainer className="max-w-[980px] pb-8">
      <header><p className="text-sm font-medium text-primary">当前设备：Creality K1</p><h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">知识库管理</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">管理 Creality K1 设备知识资料的基础工作区。</p></header>
      <section className="mt-7 rounded-xl border border-amber-600/20 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900"><p className="flex gap-2"><LockKeyhole className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><span>仅限受控本地环境使用。前端隐藏入口不能替代服务端权限控制；公开部署前必须保护管理接口。</span></p></section>
      {isPreview ? <p className="mt-6 flex gap-2 rounded-lg border border-dashed border-primary/35 bg-primary/5 px-4 py-3 text-sm leading-6 text-primary"><FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden="true" />开发预览（模拟数据）：通过 <code>?preview=admin</code> 进入，未上传文件或读取真实任务。</p> : null}
      <div className="mt-6"><DocumentUploader file={selectedFile} errorMessage={uploadError} statusMessage={statusNotice} isBusy={isBusy} onFileChange={(file) => { setSelectedFile(file); setUploadError(undefined); setStatusNotice(undefined); }} onUpload={handleUpload} /></div>
      <section className="mt-8"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-lg font-semibold text-foreground">导入任务</h2><p className="mt-1 text-sm text-muted-foreground">任务步骤由服务端状态返回；页面不会推算不可靠的百分比进度。</p></div>{isPreview ? <div className="flex flex-wrap gap-2" aria-label="导入任务开发预览"><span className="inline-flex items-center gap-1 text-xs text-primary"><FlaskConical className="size-3.5" aria-hidden="true" />模拟数据</span>{(["idle", "processing", "completed", "failed"] as ImportPreviewKind[]).map((kind) => <button key={kind} type="button" onClick={() => setPreviewKind(kind)} aria-pressed={previewKind === kind} className={`rounded-md border px-2.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30 ${previewKind === kind ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-muted-foreground hover:text-foreground"}`}>{kind === "idle" ? "空状态" : kind === "processing" ? "处理中" : kind === "completed" ? "已完成" : "失败"}</button>)}</div> : null}</div><div className="mt-4">{task ? <div>{isPreview ? <p className="mb-3 rounded-lg border border-dashed border-primary/35 bg-primary/5 px-3 py-2 text-xs text-primary">开发预览（模拟任务状态）：不表示文件已经上传、处理或入库。</p> : null}<ImportTaskProgress task={task} errorMessage={isPreview ? previewError : taskError} /></div> : <EmptyState icon={UploadCloud} title="尚未开始导入任务" description={isPreview ? "选择预览状态以检查任务界面；不会创建真实导入任务。" : "选择 PDF 或 Markdown 文件并提交后，可在此查看真实服务端任务状态。"} />}</div></section>
      <DocumentList />
    </PageContainer>
  );
}
