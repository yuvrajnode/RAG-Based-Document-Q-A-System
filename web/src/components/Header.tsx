import { formatCount } from "../lib/format";
import type { Stats } from "../lib/types";
import { MoonIcon, SunIcon } from "./Icons";

interface Props {
  stats: Stats | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onReset: () => void;
  canReset: boolean;
}

function Pill({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span
      className={`chip border border-ink-200/80 bg-white/60 text-ink-600 dark:border-ink-800
        dark:bg-ink-900/60 dark:text-ink-300 ${tone ?? ""}`}
      title={label}
    >
      <span className="text-ink-400">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}

export function Header({ stats, theme, onToggleTheme, onReset, canReset }: Props) {
  return (
    <header
      className="flex flex-wrap items-center gap-3 border-b border-ink-200/70 px-4 py-3
        dark:border-ink-800"
    >
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-600 text-white">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M6 6h9a3.5 3.5 0 0 1 0 7h-4l5 5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div>
          <h1 className="text-sm font-semibold leading-tight">Verbatim</h1>
          <p className="text-[11px] leading-tight text-ink-500">Document Q&amp;A with citations</p>
        </div>
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-1.5">
        {stats && (
          <>
            <Pill label="docs" value={String(stats.documents)} />
            <Pill label="chunks" value={formatCount(stats.chunks)} />
            <Pill label="index" value={stats.vector_store} />
            <Pill label="retrieval" value={stats.retrieval.strategy} />
            <Pill
              label="model"
              value={stats.llm.generative ? (stats.llm.model ?? "claude") : "extractive"}
              tone={stats.llm.generative ? "" : "!text-amber-600 dark:!text-amber-400"}
            />
          </>
        )}

        {canReset && (
          <button onClick={onReset} className="btn-ghost h-8 px-2.5 text-xs">
            New chat
          </button>
        )}

        <button
          onClick={onToggleTheme}
          className="btn-ghost h-8 w-8 !px-0"
          title={theme === "dark" ? "Switch to light" : "Switch to dark"}
        >
          {theme === "dark" ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
}
