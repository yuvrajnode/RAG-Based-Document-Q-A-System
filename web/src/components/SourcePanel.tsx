import { useEffect, useRef } from "react";
import { formatDuration } from "../lib/format";
import type { AskDone, SourceChunk } from "../lib/types";
import { LayersIcon } from "./Icons";

interface Props {
  sources: SourceChunk[];
  citations: number[];
  meta?: AskDone;
  active: number | null;
  onActivate: (marker: number | null) => void;
}

/** Relative bar showing how much of a passage's rank came from each retriever. */
function ScoreBar({ dense, lexical }: { dense: number; lexical: number }) {
  const total = Math.max(dense, 0) + Math.max(lexical, 0);
  const densePercent = total > 0 ? (Math.max(dense, 0) / total) * 100 : 50;

  return (
    <div className="flex items-center gap-2" title={`dense ${dense.toFixed(3)} · bm25 ${lexical.toFixed(2)}`}>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-200 dark:bg-ink-800">
        <div className="flex h-full w-full">
          <div className="h-full bg-accent-500" style={{ width: `${densePercent}%` }} />
          <div className="h-full bg-emerald-500" style={{ width: `${100 - densePercent}%` }} />
        </div>
      </div>
      <span className="w-8 shrink-0 text-right text-[10px] tabular-nums text-ink-500">
        {dense.toFixed(2)}
      </span>
    </div>
  );
}

export function SourcePanel({ sources, citations, meta, active, onActivate }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (active === null) return;
    containerRef.current
      ?.querySelector(`[data-marker="${active}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [active]);

  if (!sources.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
        <LayersIcon className="h-6 w-6 text-ink-300 dark:text-ink-700" />
        <p className="text-xs text-ink-500">
          Retrieved passages appear here, with the share of the score that came from the vector
          index versus BM25.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-baseline justify-between border-b border-ink-200/70 px-4 py-3 dark:border-ink-800">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-500">
          Sources ({sources.length})
        </h2>
        {meta && (
          <span className="text-[11px] text-ink-500">
            {meta.strategy ?? "hybrid"}
            {meta.retrieval_ms !== undefined && ` · ${formatDuration(meta.retrieval_ms)}`}
          </span>
        )}
      </div>

      <div ref={containerRef} className="flex-1 space-y-2 overflow-y-auto p-3">
        {sources.map((source, index) => {
          const marker = index + 1;
          const cited = citations.includes(marker);
          const isActive = active === marker;
          return (
            <article
              key={source.chunk_id}
              data-marker={marker}
              onMouseEnter={() => onActivate(marker)}
              onMouseLeave={() => onActivate(null)}
              className={`rounded-lg border p-3 transition-colors ${
                isActive
                  ? "border-accent-500/70 bg-accent-500/10"
                  : cited
                    ? "border-ink-200 bg-white/70 dark:border-ink-800 dark:bg-ink-900/60"
                    : "border-transparent bg-ink-100/60 opacity-70 dark:bg-ink-900/40"
              }`}
            >
              <header className="mb-2 flex items-center gap-2">
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded text-[11px]
                    font-semibold ${
                      cited
                        ? "bg-accent-600 text-white"
                        : "bg-ink-300/60 text-ink-600 dark:bg-ink-800 dark:text-ink-400"
                    }`}
                >
                  {marker}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium" title={source.document_title}>
                    {source.document_title}
                  </p>
                  <p className="truncate text-[11px] text-ink-500">
                    {source.page !== null && `page ${source.page}`}
                    {source.page !== null && source.heading && " · "}
                    {source.heading}
                    {source.page === null && !source.heading && "passage"}
                  </p>
                </div>
                {!cited && (
                  <span className="shrink-0 text-[10px] uppercase tracking-wide text-ink-400">
                    unused
                  </span>
                )}
              </header>

              <p className="max-h-32 overflow-hidden text-xs leading-relaxed text-ink-600 dark:text-ink-300">
                {source.text}
              </p>

              <footer className="mt-2.5">
                <ScoreBar dense={source.dense_score} lexical={source.lexical_score} />
              </footer>
            </article>
          );
        })}

        <p className="px-1 pt-1 text-[10px] leading-relaxed text-ink-400">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-500 align-middle" /> vector
          similarity · <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 align-middle" />{" "}
          BM25. Greyed passages were retrieved but not cited in the answer.
        </p>
      </div>
    </div>
  );
}
