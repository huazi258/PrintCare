import { Search } from "lucide-react";

import type { HistoryFilter } from "./history-state";

type HistoryFiltersProps = {
  filter: HistoryFilter;
  query: string;
  onFilterChange: (filter: HistoryFilter) => void;
  onQueryChange: (query: string) => void;
};

const filters: { value: HistoryFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "qa", label: "知识问答" },
  { value: "diagnosis", label: "智能诊断" },
];

export function HistoryFilters({ filter, query, onFilterChange, onQueryChange }: HistoryFiltersProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="relative w-full sm:max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <label className="sr-only" htmlFor="history-search">搜索历史记录</label>
        <input
          id="history-search"
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索问题或故障描述"
          className="h-10 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
      </div>
      <div className="flex gap-1 overflow-x-auto rounded-lg bg-muted p-1" aria-label="记录类型筛选">
        {filters.map((item) => (
          <button
            type="button"
            key={item.value}
            onClick={() => onFilterChange(item.value)}
            aria-pressed={filter === item.value}
            className={`shrink-0 rounded-md px-3 py-1.5 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-primary/30 ${
              filter === item.value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
