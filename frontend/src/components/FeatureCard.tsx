import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

interface FeatureCardProps {
  title: string;
  description: string;
  action: string;
  to: string;
  icon: LucideIcon;
}

export function FeatureCard({ title, description, action, to, icon: Icon }: FeatureCardProps) {
  return (
    <Link
      className="group flex min-h-52 flex-col rounded-xl border border-border bg-card p-6 outline-none transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring"
      to={to}
    >
      <span className="flex size-10 items-center justify-center rounded-lg bg-muted text-primary">
        <Icon aria-hidden="true" size={20} strokeWidth={1.8} />
      </span>
      <h2 className="mt-5 text-lg font-semibold text-foreground">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
      <span className="mt-auto flex items-center gap-2 pt-5 text-sm font-medium text-primary">
        {action}
        <ArrowRight aria-hidden="true" className="transition-transform duration-200 group-hover:translate-x-0.5" size={16} />
      </span>
    </Link>
  );
}
