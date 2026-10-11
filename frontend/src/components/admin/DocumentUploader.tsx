import { FileUp, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";

type DocumentUploaderProps = {
  file: File | null;
  errorMessage?: string;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
};

export function DocumentUploader({ file, errorMessage, onFileChange, onUpload }: DocumentUploaderProps) {
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-[0_2px_10px_rgba(27,36,48,0.04)]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">导入设备资料</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">服务端将在实际上传时校验文件格式与大小；本页面不预设未确认的限制。</p>
        </div>
        <span className="inline-flex w-fit rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">Creality K1</span>
      </div>

      <label htmlFor="knowledge-file" className="mt-5 flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-border bg-background px-5 py-8 text-center transition hover:border-primary/50 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
        <FileUp className="size-7 text-primary" aria-hidden="true" />
        <span className="mt-3 text-sm font-medium text-foreground">选择本地资料文件</span>
        <span className="mt-1 text-xs leading-5 text-muted-foreground">文件格式与大小以服务端实际校验结果为准</span>
        <input id="knowledge-file" type="file" className="sr-only" onChange={(event) => onFileChange(event.target.files?.[0] ?? null)} />
      </label>

      {file ? (
        <div className="mt-4 flex flex-col gap-3 rounded-lg border border-border bg-muted/60 p-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="min-w-0 truncate text-sm text-foreground">已选择：{file.name}</p>
          <button type="button" onClick={() => onFileChange(null)} className="inline-flex items-center gap-1.5 self-start rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-card hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"><Trash2 className="size-3.5" aria-hidden="true" />清除</button>
        </div>
      ) : null}
      {errorMessage ? <p role="alert" className="mt-4 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{errorMessage}</p> : null}
      <div className="mt-5 flex justify-end"><Button type="button" disabled={!file} onClick={onUpload}><Upload className="size-4" aria-hidden="true" />上传并导入</Button></div>
    </section>
  );
}
