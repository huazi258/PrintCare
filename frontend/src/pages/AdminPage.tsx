import { useState } from "react";
import { FlaskConical, LockKeyhole, UploadCloud } from "lucide-react";

import { DocumentList } from "@/components/admin/DocumentList";
import { DocumentUploader } from "@/components/admin/DocumentUploader";
import { importPreviewTasks, type ImportPreviewKind } from "@/components/admin/admin-state";
import { ImportTaskProgress } from "@/components/admin/ImportTaskProgress";
import { EmptyState } from "@/components/EmptyState";
import { PageContainer } from "@/components/PageContainer";

export function AdminPage() {
  const isPreview = import.meta.env.DEV;
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | undefined>();
  const [previewKind, setPreviewKind] = useState<ImportPreviewKind>("idle");
  const task = previewKind === "idle" ? null : importPreviewTasks[previewKind];
  const previewError = previewKind === "failed" ? "开发预览：此错误仅用于验证导入失败提示，未发生真实上传或导入。" : undefined;

  function handleUpload() {
    setUploadError("上传服务尚待联调。已选文件仍保留在页面中，未发送到服务器，也没有创建导入任务。");
  }

  return (
    <PageContainer className="max-w-[980px] pb-8">
      <header><p className="text-sm font-medium text-primary">当前设备：Creality K1</p><h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">知识库管理</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">管理 Creality K1 设备知识资料的基础工作区。</p></header>
      <section className="mt-7 rounded-xl border border-amber-600/20 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900"><p className="flex gap-2"><LockKeyhole className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><span>仅限受控本地环境使用。前端隐藏入口不能替代服务端权限控制；公开部署前必须保护管理接口。</span></p></section>
      <div className="mt-6"><DocumentUploader file={selectedFile} errorMessage={uploadError} onFileChange={(file) => { setSelectedFile(file); setUploadError(undefined); }} onUpload={handleUpload} /></div>
      <section className="mt-8"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-lg font-semibold text-foreground">导入任务</h2><p className="mt-1 text-sm text-muted-foreground">任务步骤由服务端状态返回；页面不会推算不可靠的百分比进度。</p></div>{isPreview ? <div className="flex flex-wrap gap-2" aria-label="导入任务开发预览"><span className="inline-flex items-center gap-1 text-xs text-primary"><FlaskConical className="size-3.5" aria-hidden="true" />模拟数据</span>{(["idle", "processing", "completed", "failed"] as ImportPreviewKind[]).map((kind) => <button key={kind} type="button" onClick={() => setPreviewKind(kind)} aria-pressed={previewKind === kind} className={`rounded-md border px-2.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30 ${previewKind === kind ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-muted-foreground hover:text-foreground"}`}>{kind === "idle" ? "空状态" : kind === "processing" ? "处理中" : kind === "completed" ? "已完成" : "失败"}</button>)}</div> : null}</div><div className="mt-4">{task ? <div><p className="mb-3 rounded-lg border border-dashed border-primary/35 bg-primary/5 px-3 py-2 text-xs text-primary">开发预览（模拟任务状态）：不表示文件已经上传、处理或入库。</p><ImportTaskProgress task={task} errorMessage={previewError} /></div> : <EmptyState icon={UploadCloud} title="尚未开始导入任务" description="选择文件后可查看上传入口；真实任务状态将在后续服务端联调后读取。" />}</div></section>
      <DocumentList />
    </PageContainer>
  );
}
