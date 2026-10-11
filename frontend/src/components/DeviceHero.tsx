import { ImageOff } from "lucide-react";

export function DeviceHero() {
  return (
    <section aria-labelledby="device-heading" className="grid overflow-hidden rounded-xl border border-border bg-card shadow-sm md:grid-cols-[minmax(250px,0.9fr)_minmax(0,1.1fr)]">
      <div className="flex min-h-64 items-center justify-center border-b border-border bg-muted/60 p-8 md:min-h-[320px] md:border-r md:border-b-0">
        <div className="flex max-w-52 flex-col items-center gap-3 text-center text-muted-foreground">
          <ImageOff aria-hidden="true" size={36} strokeWidth={1.4} />
          <div>
            <p className="text-sm font-medium text-foreground">产品图片待补充</p>
            <p className="mt-1 text-xs leading-5">未添加可确认再分发许可的 Creality K1 产品照片。</p>
          </div>
        </div>
      </div>
      <div className="flex flex-col justify-center p-6 sm:p-8">
        <p className="text-sm font-medium text-primary">当前支持设备</p>
        <h1 id="device-heading" className="mt-3 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          Creality K1
        </h1>
        <p className="mt-4 max-w-xl text-base leading-7 text-muted-foreground">
          PrintCare AI 为 Creality K1 用户提供基于设备资料的知识查询与故障排查支持。
        </p>
        <p className="mt-5 text-sm text-muted-foreground">V1 当前仅支持 K1；不会读取或控制实体打印机。</p>
      </div>
    </section>
  );
}
