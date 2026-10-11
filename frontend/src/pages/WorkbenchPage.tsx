import { BookOpenText, BrainCircuit, Clock3 } from "lucide-react";
import { Link } from "react-router-dom";
import { DeviceHero } from "@/components/DeviceHero";
import { EmptyState } from "@/components/EmptyState";
import { FeatureCard } from "@/components/FeatureCard";
import { PageContainer } from "@/components/PageContainer";

export function WorkbenchPage() {
  return (
    <PageContainer className="space-y-8 sm:space-y-10">
      <div>
        <p className="text-sm font-medium text-primary">设备支持工作台</p>
        <p className="mt-2 text-sm text-muted-foreground">选择所需支持方式，开始使用 K1 设备资料。</p>
      </div>

      <DeviceHero />

      <section aria-labelledby="feature-heading">
        <div className="mb-4">
          <h2 id="feature-heading" className="text-xl font-semibold tracking-tight text-foreground">开始使用</h2>
          <p className="mt-1 text-sm text-muted-foreground">问答与诊断为独立入口，请根据当前需求主动选择。</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <FeatureCard
            action="开始提问"
            description="设备使用说明、参数查询与技术指导"
            icon={BookOpenText}
            title="知识问答"
            to="/qa"
          />
          <FeatureCard
            action="开始诊断"
            description="描述故障现象，逐步排查可能原因"
            icon={BrainCircuit}
            title="智能诊断"
            to="/diagnosis"
          />
        </div>
      </section>

      <section aria-labelledby="recent-heading">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h2 id="recent-heading" className="text-xl font-semibold tracking-tight text-foreground">最近使用</h2>
            <p className="mt-1 text-sm text-muted-foreground">仅显示当前浏览器关联的记录。</p>
          </div>
          <Link className="shrink-0 rounded-md px-2 py-1 text-sm font-medium text-primary outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring" to="/history">
            查看全部
          </Link>
        </div>
        <EmptyState
          description="当前没有可显示的问答或诊断记录。后续完成历史接入后，最近使用内容会显示在这里。"
          icon={Clock3}
          title="暂无最近使用"
        />
      </section>
    </PageContainer>
  );
}
