import { useEffect, useRef, useState } from "react";
import { FlaskConical, KeyRound, LockKeyhole, UploadCloud } from "lucide-react";

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
import { Button } from "@/components/ui/button";
import { ApiError } from "@/services/http";
import { printCareApi } from "@/services/printcare-api";
import type { ImportTaskStatus } from "@/types/api";

function adminAccessMessage(error: ApiError) {
  return error.status === 503
    ? "导入服务尚未配置管理员密钥，已拒绝管理操作。请由受控环境的服务管理员完成配置。"
    : "管理员密钥无效或已失效。请重新输入后再试。";
}

export function AdminPage() {
  const isPreview = import.meta.env.DEV && new URLSearchParams(window.location.search).get("preview") === "admin";
  const [adminKey, setAdminKey] = useState<string | null>(null);
  const [adminKeyDraft, setAdminKeyDraft] = useState("");
  const [adminAccessError, setAdminAccessError] = useState<string | undefined>();
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

  const lockAdminAccess = () => {
    stopPolling();
    uploadAbortRef.current?.abort();
    activeTaskIdRef.current = null;
    uploadInFlightRef.current = false;
    setIsBusy(false);
    setLiveTask(null);
    setStatusNotice(undefined);
    setTaskError(undefined);
    setAdminKey(null);
  };

  const handleAdminApiError = (error: unknown) => {
    if (!(error instanceof ApiError) || (error.status !== 401 && error.status !== 503)) return false;
    lockAdminAccess();
    setAdminAccessError(adminAccessMessage(error));
    return true;
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      stopPolling();
      uploadAbortRef.current?.abort();
    };
  }, []);

  const pollTask = async (taskId: string, key: string, completedAttempts: number) => {
    if (activeTaskIdRef.current !== taskId) return;
    const controller = new AbortController();
    statusAbortRef.current = controller;
    try {
      const nextTask = await printCareApi.getImportStatus(taskId, key, { signal: controller.signal });
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
        void pollTask(taskId, key, nextAttempt);
      }, IMPORT_POLL_INTERVAL_MS);
    } catch (error) {
      if (controller.signal.aborted || !mountedRef.current || activeTaskIdRef.current !== taskId) return;
      if (handleAdminApiError(error)) return;
      activeTaskIdRef.current = null;
      uploadInFlightRef.current = false;
      setIsBusy(false);
      setTaskError(error instanceof Error ? `读取导入任务状态失败：${error.message}` : "读取导入任务状态失败，请稍后重试。");
    }
  };

  const handleUpload = async () => {
    const file = selectedFile;
    const key = adminKey;
    if (!file || !canStartImport(true, isBusy) || uploadInFlightRef.current) return;
    if (isPreview) {
      setUploadError("开发预览不会上传文件或创建导入任务。请在不带 ?preview=admin 的页面执行真实导入。");
      return;
    }
    if (!key) return;

    stopPolling();
    setUploadError(undefined);
    setTaskError(undefined);
    setStatusNotice("正在上传文件并创建导入任务…");
    uploadInFlightRef.current = true;
    setIsBusy(true);
    const controller = new AbortController();
    uploadAbortRef.current = controller;
    try {
      const response = await printCareApi.uploadDocument(file, "creality-k1", key, { signal: controller.signal });
      if (!response.task_id) throw new Error("上传服务未返回任务标识。");
      if (!mountedRef.current) return;
      activeTaskIdRef.current = response.task_id;
      setLiveTask({ status: "pending", running_list: [], done_list: [], durations: {} });
      setStatusNotice("文件已提交，正在读取服务端导入任务状态…");
      await pollTask(response.task_id, key, 0);
    } catch (error) {
      if (controller.signal.aborted || !mountedRef.current) return;
      if (handleAdminApiError(error)) return;
      activeTaskIdRef.current = null;
      uploadInFlightRef.current = false;
      setIsBusy(false);
      setStatusNotice(undefined);
      setUploadError(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "上传失败，请稍后重试。");
    }
  };

  const unlockAdminAccess = () => {
    if (!adminKeyDraft.trim()) return;
    setAdminKey(adminKeyDraft);
    setAdminKeyDraft("");
    setAdminAccessError(undefined);
  };

  const canUseManagementTools = isPreview || adminKey !== null;

  return (
    <PageContainer className="max-w-[980px] pb-8">
      <header>
        <p className="text-sm font-medium text-primary">当前设备：Creality K1</p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">知识库管理</h1>
          {!isPreview && adminKey ? <Button type="button" variant="outline" size="sm" onClick={lockAdminAccess}>锁定管理操作</Button> : null}
        </div>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">管理 Creality K1 设备知识资料的基础工作区。</p>
      </header>
      <section className="mt-7 rounded-xl border border-amber-600/20 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
        <p className="flex gap-2"><LockKeyhole className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><span>仅限受控本地环境使用。管理操作由服务端管理员密钥保护；公开部署前仍须配置 HTTPS 和更完整的访问控制。</span></p>
      </section>
      {isPreview ? <p className="mt-6 flex gap-2 rounded-lg border border-dashed border-primary/35 bg-primary/5 px-4 py-3 text-sm leading-6 text-primary"><FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden="true" />开发预览（模拟数据）：通过 <code>?preview=admin</code> 进入，未上传文件或读取真实任务。</p> : null}

      {!canUseManagementTools ? (
        <section className="mt-6 rounded-xl border border-border bg-card p-5 shadow-[0_2px_10px_rgba(27,36,48,0.04)]">
          <div className="flex gap-3"><KeyRound className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" /><div><h2 className="text-lg font-semibold text-foreground">解锁管理操作</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">请输入由受控环境管理员配置的密钥。密钥仅保存在当前页面运行内存中，刷新或锁定后即会清除。</p></div></div>
          <form className="mt-5 max-w-xl" onSubmit={(event) => { event.preventDefault(); unlockAdminAccess(); }}>
            <label htmlFor="admin-api-key" className="text-sm font-medium text-foreground">管理员密钥</label>
            <div className="mt-2 flex flex-col gap-3 sm:flex-row">
              <input id="admin-api-key" type="password" autoComplete="off" value={adminKeyDraft} onChange={(event) => setAdminKeyDraft(event.target.value)} className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring" aria-describedby="admin-api-key-help" />
              <Button type="submit" disabled={!adminKeyDraft.trim()}>解锁</Button>
            </div>
            <p id="admin-api-key-help" className="mt-2 text-xs leading-5 text-muted-foreground">不会写入 localStorage、地址栏、前端环境变量或构建产物。</p>
            {adminAccessError ? <p role="alert" className="mt-3 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{adminAccessError}</p> : null}
          </form>
        </section>
      ) : (
        <>
          <div className="mt-6"><DocumentUploader file={selectedFile} errorMessage={uploadError} statusMessage={statusNotice} isBusy={isBusy} onFileChange={(file) => { setSelectedFile(file); setUploadError(undefined); setStatusNotice(undefined); }} onUpload={handleUpload} /></div>
          <section className="mt-8">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div><h2 className="text-lg font-semibold text-foreground">导入任务</h2><p className="mt-1 text-sm text-muted-foreground">任务步骤由服务端状态返回；页面不会推算不可靠的百分比进度。</p></div>
              {isPreview ? <div className="flex flex-wrap gap-2" aria-label="导入任务开发预览"><span className="inline-flex items-center gap-1 text-xs text-primary"><FlaskConical className="size-3.5" aria-hidden="true" />模拟数据</span>{(["idle", "processing", "completed", "failed"] as ImportPreviewKind[]).map((kind) => <button key={kind} type="button" onClick={() => setPreviewKind(kind)} aria-pressed={previewKind === kind} className={`rounded-md border px-2.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30 ${previewKind === kind ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-muted-foreground hover:text-foreground"}`}>{kind === "idle" ? "空状态" : kind === "processing" ? "处理中" : kind === "completed" ? "已完成" : "失败"}</button>)}</div> : null}
            </div>
            <div className="mt-4">
              {task ? <div>{isPreview ? <p className="mb-3 rounded-lg border border-dashed border-primary/35 bg-primary/5 px-3 py-2 text-xs text-primary">开发预览（模拟任务状态）：不表示文件已经上传、处理或入库。</p> : null}<ImportTaskProgress task={task} errorMessage={isPreview ? previewError : taskError} /></div> : <EmptyState icon={UploadCloud} title="尚未开始导入任务" description={isPreview ? "选择预览状态以检查任务界面；不会创建真实导入任务。" : "选择 PDF 或 Markdown 文件并提交后，可在此查看真实服务端任务状态。"} />}
            </div>
          </section>
        </>
      )}
      <DocumentList />
    </PageContainer>
  );
}
