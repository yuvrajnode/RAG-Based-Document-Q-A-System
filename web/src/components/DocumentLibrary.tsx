import { useCallback, useRef, useState, type DragEvent } from "react";
import { formatBytes, formatRelative, typeLabel, typeTone } from "../lib/format";
import type { DocumentSummary, UploadOutcome } from "../lib/types";
import { DocIcon, TrashIcon, UploadIcon } from "./Icons";

interface Props {
  documents: DocumentSummary[];
  selected: string[];
  uploading: boolean;
  onSelect: (id: string) => void;
  onClearSelection: () => void;
  onUpload: (files: File[]) => Promise<UploadOutcome[]>;
  onRemove: (id: string) => Promise<void>;
}

const ACCEPT = ".pdf,.docx,.txt,.md,.markdown,.html,.htm,.csv,.json";

export function DocumentLibrary({
  documents,
  selected,
  uploading,
  onSelect,
  onClearSelection,
  onUpload,
  onRemove,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files?.length) return;
      const outcomes = await onUpload(Array.from(files));
      setRejected(outcomes.filter((outcome) => !outcome.ok).map((o) => `${o.filename}: ${o.detail}`));
    },
    [onUpload],
  );

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(false);
      void handleFiles(event.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <div className="flex h-full flex-col gap-3">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => event.key === "Enter" && inputRef.current?.click()}
        className={`group cursor-pointer rounded-xl border-2 border-dashed px-4 py-6 text-center
          transition-colors ${
            dragging
              ? "border-accent-500 bg-accent-500/10"
              : "border-ink-300/70 hover:border-accent-400 hover:bg-accent-500/5 dark:border-ink-700"
          }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(event) => {
            void handleFiles(event.target.files);
            event.target.value = "";
          }}
        />
        <UploadIcon
          className={`mx-auto h-6 w-6 ${uploading ? "animate-pulse text-accent-500" : "text-ink-400"}`}
        />
        <p className="mt-2 text-sm font-medium">
          {uploading ? "Indexing..." : "Drop files or browse"}
        </p>
        <p className="mt-0.5 text-xs text-ink-500">PDF, DOCX, MD, TXT, HTML, CSV, JSON</p>
      </div>

      {rejected.length > 0 && (
        <div className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-600 dark:text-rose-300">
          {rejected.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between px-1">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-500">
          Library ({documents.length})
        </h2>
        {selected.length > 0 && (
          <button onClick={onClearSelection} className="text-xs text-accent-600 dark:text-accent-400">
            clear filter
          </button>
        )}
      </div>

      <div className="-mx-1 flex-1 space-y-1 overflow-y-auto px-1 pb-1">
        {documents.length === 0 && (
          <p className="px-1 py-6 text-center text-xs text-ink-500">
            Nothing indexed yet. Add a document to start asking questions.
          </p>
        )}

        {documents.map((document) => {
          const isSelected = selected.includes(document.id);
          const bytes = Number(document.metadata?.bytes ?? 0);
          return (
            <div
              key={document.id}
              onClick={() => onSelect(document.id)}
              className={`group flex cursor-pointer items-start gap-2.5 rounded-lg border px-2.5 py-2
                transition-colors ${
                  isSelected
                    ? "border-accent-500/60 bg-accent-500/10"
                    : "border-transparent hover:border-ink-200 hover:bg-ink-100/70 dark:hover:border-ink-800 dark:hover:bg-ink-800/50"
                }`}
            >
              <DocIcon className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium" title={document.title}>
                  {document.title}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-500">
                  <span className={`chip ${typeTone(document.source_type)}`}>
                    {typeLabel(document.source_type)}
                  </span>
                  <span>{document.chunk_count} chunks</span>
                  {bytes > 0 && <span>· {formatBytes(bytes)}</span>}
                  <span>· {formatRelative(document.created_at)}</span>
                </div>
              </div>
              <button
                title="Remove from the index"
                onClick={(event) => {
                  event.stopPropagation();
                  void onRemove(document.id);
                }}
                className="rounded p-1 text-ink-400 opacity-0 transition hover:bg-rose-500/15
                  hover:text-rose-500 focus-visible:opacity-100 group-hover:opacity-100"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
